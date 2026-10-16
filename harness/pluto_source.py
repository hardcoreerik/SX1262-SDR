# SPDX-License-Identifier: GPL-3.0-only
# Part of the SX1262-SDR bench harness. Credits: see harness/README.md.
"""PlutoSDR (or clone) CW tone source for cabled bench tests.

Backends, tried in order unless --backend is given:
  adi   pyadi-iio (adi.Pluto): tx_lo, tx_hardwaregain_chan0, dds_single_tone/dds_dual_tone
  iio   pylibiio only: the same IIO attributes written directly (ad9361-phy, cf-ad9361-dds-core-lpc)
  sim   SimBench model, no hardware (--dry-run / --sim)

The tone is LO + baseband DDS offset. The TX LO range is read from the radio at runtime
(ad9361-phy altvoltage1 "frequency_available"), never assumed: stock AD9363 Plutos report
about 325 MHz-3.8 GHz, AD9364-hacked or AD9361 clones report about 70 MHz-6 GHz.

SAFETY: hardware TX is refused unless the configured fixed attenuation between the Pluto
and the DUT is at least --min-fixed-atten-db (default 30) and the requested hardwaregain is
at or below --max-gain-db (default -20). Cabled, shielded bench use only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time

GAIN_MIN_DB = -89.75  # AD936x TX hardwaregain floor as the driver reports it ("hardwaregain_available")
DDS_TX1 = {"I_F1": "altvoltage0", "I_F2": "altvoltage1", "Q_F1": "altvoltage2", "Q_F2": "altvoltage3"}


def parse_available(text):
    """'[46875001 1 6000000000]' -> (min, step, max) as ints."""
    nums = [int(float(x)) for x in re.findall(r"-?\d+(?:\.\d+)?", text or "")]
    if len(nums) != 3:
        raise ValueError("unexpected frequency_available: %r" % text)
    return tuple(nums)


class SafetyError(RuntimeError):
    pass


class PlutoSource:
    def __init__(self, uri="ip:192.168.2.1", backend="auto", sim_bench=None,
                 fixed_atten_db=None, min_fixed_atten_db=30.0, max_gain_db=-20.0,
                 bb_offset_hz=1_000_000, dds_invert_q=False):
        self.uri, self.backend = uri, backend
        self.bench = sim_bench
        self.fixed_atten_db = fixed_atten_db
        self.min_fixed_atten_db = min_fixed_atten_db
        self.max_gain_db = max_gain_db
        self.bb_offset_hz = int(bb_offset_hz)
        self.dds_invert_q = dds_invert_q
        self.info = {}
        self.range_hz = None
        self.enabled = False
        self.state = {"lo": None, "tones": [], "gain": GAIN_MIN_DB}
        self._sdr = self._ctx = None
        self._open()

    # -------------------------------------------------------------- open --
    def _open(self):
        if self.backend in ("sim", "dry-run") or self.bench is not None:
            from sim import SimBench
            self.bench = self.bench or SimBench()
            self.backend = "sim"
            lo, hi = self.bench.pluto_range_hz
            self.range_hz = (int(lo), 1, int(hi))
            self.info = {"hw_model": "SIMULATED Pluto", "fw_version": "sim", "backend": "sim"}
            return
        errors = []
        if self.backend in ("auto", "adi"):
            try:
                import adi  # pyadi-iio
                self._sdr = adi.Pluto(self.uri)
                self._ctx = self._sdr.ctx
                self.backend = "adi"
            except Exception as e:  # noqa: BLE001
                errors.append("adi: %s" % e)
                if self.backend == "adi":
                    raise
        if self._ctx is None and self.backend in ("auto", "iio"):
            import iio  # pylibiio
            self._ctx = iio.Context(self.uri)
            self.backend = "iio"
        if self._ctx is None:
            raise RuntimeError("no Pluto backend: " + "; ".join(errors))
        self._phy = self._ctx.find_device("ad9361-phy")
        self._dds = self._ctx.find_device("cf-ad9361-dds-core-lpc")
        if self._phy is None or self._dds is None:
            raise RuntimeError("ad9361-phy / cf-ad9361-dds-core-lpc not found at %s" % self.uri)
        self.info = {k: v for k, v in self._ctx.attrs.items()}
        self.info["backend"] = self.backend
        self.info["backend_errors"] = errors
        txlo = self._phy.find_channel("altvoltage1", True)
        self.range_hz = parse_available(txlo.attrs["frequency_available"].value)
        try:
            fs = float(self._dds.find_channel("voltage0", True).attrs["sampling_frequency"].value)
        except Exception:  # noqa: BLE001
            fs = None
        self.info["dds_sampling_frequency"] = fs
        self.info["tx_lo_range_hz"] = self.range_hz
        # Make sure nothing is radiating from a previous session.
        self.disable()

    # ------------------------------------------------------------ helpers --
    def covers(self, hz):
        lo, _, hi = self.range_hz
        return lo + self.bb_offset_hz <= hz <= hi

    def _check_safety(self, gain_db):
        if self.backend == "sim":
            return
        if self.fixed_atten_db is None or self.fixed_atten_db < self.min_fixed_atten_db:
            raise SafetyError("refusing TX: fixed attenuation %s dB < required %s dB. Fit the fixed "
                              "attenuator and pass --fixed-atten-db." % (self.fixed_atten_db, self.min_fixed_atten_db))
        if gain_db > self.max_gain_db:
            raise SafetyError("refusing TX: hardwaregain %.2f dB above limit %.2f dB" % (gain_db, self.max_gain_db))

    def _attr(self, dev, ch, name, value, output=True):
        dev.find_channel(ch, output).attrs[name].value = str(value)

    # ---------------------------------------------------------------- API --
    def set_tone(self, rf_hz, gain_db, extra_offsets_hz=()):
        """One tone at rf_hz (LO = rf_hz - bb_offset). extra_offsets_hz adds a second DDS tone
        at rf_hz + offset (two-tone IMD); each tone is then 6 dB down."""
        gain_db = max(GAIN_MIN_DB, float(gain_db))
        self._check_safety(gain_db)
        if not self.covers(rf_hz):
            raise ValueError("%.0f Hz outside detected TX range %s" % (rf_hz, self.range_hz))
        lo = int(round(rf_hz - self.bb_offset_hz))
        bbs = [self.bb_offset_hz] + [self.bb_offset_hz + int(o) for o in extra_offsets_hz]
        scale_db = 0.0 if len(bbs) == 1 else -6.0
        self.state = {"lo": lo, "tones": [(b, scale_db) for b in bbs], "gain": gain_db}
        if self.backend == "sim":
            self.bench.pluto.update(enabled=True, lo=lo, tones=list(self.state["tones"]), gain=gain_db)
        elif self.backend == "adi":
            s = self._sdr
            s.tx_hardwaregain_chan0 = GAIN_MIN_DB  # never step up in power while retuning
            s.tx_lo = lo
            sc = 0.9 if len(bbs) == 1 else 0.45
            if len(bbs) == 1:
                s.dds_single_tone(bbs[0], sc, 0)
            else:
                s.dds_dual_tone(bbs[0], sc, bbs[1], sc, 0)
            self._attr(self._phy, "altvoltage1", "powerdown", 0)
            s.tx_hardwaregain_chan0 = gain_db
        else:
            self._attr(self._phy, "voltage0", "hardwaregain", GAIN_MIN_DB)
            self._attr(self._phy, "altvoltage1", "frequency", lo)
            sc = 0.9 if len(bbs) == 1 else 0.45
            for i, key in enumerate(("F1", "F2")):
                f = bbs[i] if i < len(bbs) else 0
                on = i < len(bbs)
                for iq, ph in (("I", 90000), ("Q", 0 if not self.dds_invert_q else 180000)):
                    ch = DDS_TX1["%s_%s" % (iq, key)]
                    self._attr(self._dds, ch, "frequency", f)
                    self._attr(self._dds, ch, "scale", sc if on else 0)
                    self._attr(self._dds, ch, "phase", ph)
            for ch in ("altvoltage0", "altvoltage2"):
                self._attr(self._dds, ch, "raw", 1)
            self._attr(self._phy, "altvoltage1", "powerdown", 0)
            self._attr(self._phy, "voltage0", "hardwaregain", gain_db)
        self.enabled = True
        time.sleep(0.0 if self.backend == "sim" else 0.05)
        return dict(self.state)

    def set_gain(self, gain_db):
        if self.state["lo"] is None:
            raise RuntimeError("set_tone first")
        gain_db = max(GAIN_MIN_DB, float(gain_db))
        self._check_safety(gain_db)
        self.state["gain"] = gain_db
        if self.backend == "sim":
            self.bench.pluto["gain"] = gain_db
        elif self.backend == "adi":
            self._sdr.tx_hardwaregain_chan0 = gain_db
        else:
            self._attr(self._phy, "voltage0", "hardwaregain", gain_db)

    def disable(self):
        """Lowest gain, DDS off, TX LO powered down. Safe to call any time."""
        self.enabled = False
        if self.backend == "sim":
            self.bench.pluto["enabled"] = False
            return
        try:
            if self.backend == "adi":
                self._sdr.tx_hardwaregain_chan0 = GAIN_MIN_DB
                self._sdr.disable_dds()
            else:
                self._attr(self._phy, "voltage0", "hardwaregain", GAIN_MIN_DB)
                for ch in DDS_TX1.values():
                    self._attr(self._dds, ch, "scale", 0)
            self._attr(self._phy, "altvoltage1", "powerdown", 1)
        except Exception as e:  # noqa: BLE001
            print("pluto: disable warning: %s" % e, file=sys.stderr)

    def describe(self):
        return {"uri": self.uri, "backend": self.backend, "range_hz": self.range_hz,
                "bb_offset_hz": self.bb_offset_hz, "info": self.info}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uri", default="ip:192.168.2.1")
    ap.add_argument("--backend", default="auto", choices=["auto", "adi", "iio", "sim"])
    ap.add_argument("--dry-run", "--sim", dest="sim", action="store_true", help="no hardware")
    ap.add_argument("--detect", action="store_true", help="print detected model and TX range, then exit")
    ap.add_argument("--freq", type=float, help="tone frequency in Hz (LO + offset)")
    ap.add_argument("--offset", type=float, default=1e6, help="baseband DDS offset in Hz")
    ap.add_argument("--gain", type=float, default=-60.0, help="TX hardwaregain in dB (<= 0)")
    ap.add_argument("--fixed-atten-db", type=float, help="fixed attenuation fitted at the Pluto output")
    ap.add_argument("--max-gain-db", type=float, default=-20.0)
    ap.add_argument("--seconds", type=float, default=5.0, help="how long to hold the tone")
    ap.add_argument("--off", action="store_true", help="disable TX and exit")
    a = ap.parse_args(argv)
    src = PlutoSource(a.uri, "sim" if a.sim else a.backend, fixed_atten_db=a.fixed_atten_db,
                      max_gain_db=a.max_gain_db, bb_offset_hz=a.offset)
    if a.detect or a.freq is None and not a.off:
        print(json.dumps(src.describe(), indent=2, default=str))
        return 0
    if a.off:
        src.disable(); print("pluto: TX disabled"); return 0
    try:
        st = src.set_tone(a.freq, a.gain)
        print("pluto: tone %.0f Hz (LO %d + %d) gain %.2f dB for %.1f s" %
              (a.freq, st["lo"], src.bb_offset_hz, st["gain"], a.seconds))
        time.sleep(a.seconds if not a.sim else 0)
    finally:
        src.disable()
        print("pluto: TX disabled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
