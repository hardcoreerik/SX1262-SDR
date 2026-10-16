# SPDX-License-Identifier: GPL-3.0-only
# Part of the SX1262-SDR bench harness. Credits: see harness/README.md.
"""RTL-SDR reference receiver: checks that the Pluto output is clean before it is trusted.

It measures, relative to the fundamental tone (dBc): the Pluto LO leakage, the Pluto
sideband image, 2f and 3f harmonics, and any extra "alias" frequencies the caller names
(for example the DUT's own image frequency). Frequencies outside the dongle's tuning range
are reported as unmeasured, never as clean.

Backends: pyrtlsdr (librtlsdr via Python), rtl_power (command-line, single sweep), sim.
Gain is always fixed (never AGC) so levels are comparable. Levels are uncalibrated dBFS:
only differences (dBc, dB steps) are meaningful.

Harmonic sanity: a strong fundamental can create 2f/3f inside the dongle itself. With
harmonic_linearity=True each harmonic is re-measured with the source 10 dB lower: a
source harmonic falls about 10 dB, a dongle-generated 2nd/3rd falls about 20/30 dB.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile


class RtlReference:
    def __init__(self, backend="auto", gain_db=20.0, ppm=0, sim_bench=None,
                 range_hz=(24e6, 1766e6), rbw_hz=1000.0, device_index=0):
        self.gain_db, self.ppm, self.rbw = gain_db, int(ppm), rbw_hz
        self.range_hz = range_hz  # typical R820T/R828D tuner range; set yours in config
        self.bench = sim_bench
        self.backend = backend
        self.device_index = device_index
        self.note = ""
        self._sdr = None
        self._open()

    def _open(self):
        if self.backend == "sim" or self.bench is not None:
            from sim import SimBench
            self.bench = self.bench or SimBench()
            self.backend = "sim"
            return
        if self.backend in ("auto", "pyrtlsdr"):
            try:
                from rtlsdr import RtlSdr
                self._sdr = RtlSdr(self.device_index)
                self._sdr.sample_rate = 2.048e6
                self._sdr.gain = self.gain_db
                if self.ppm:
                    self._sdr.freq_correction = self.ppm
                self.backend = "pyrtlsdr"
                return
            except Exception as e:  # noqa: BLE001  (e.g. DLL/pyrtlsdr version mismatch)
                self.note = "pyrtlsdr unavailable: %s" % e
                if self.backend == "pyrtlsdr":
                    raise
        if shutil.which("rtl_power"):
            self.backend = "rtl_power"
            return
        raise RuntimeError("no RTL-SDR backend (%s; rtl_power not on PATH)" % self.note)

    def close(self):
        if self._sdr is not None:
            self._sdr.close()

    def in_range(self, hz):
        return self.range_hz[0] <= hz <= self.range_hz[1]

    # ------------------------------------------------------- measurement --
    def peak(self, hz, span_hz=20e3):
        """(peak_hz, peak_db, floor_db) within hz +- span/2, or None if out of range."""
        if not self.in_range(hz):
            return None
        if self.backend == "sim":
            return self.bench.rtl_peak(hz, span_hz, self.rbw)
        if self.backend == "pyrtlsdr":
            return self._peak_pyrtlsdr(hz, span_hz)
        return self._peak_rtl_power(hz, span_hz)

    def _peak_pyrtlsdr(self, hz, span_hz):
        import numpy as np
        off = 300e3  # keep the dongle's DC spike away from the tone
        self._sdr.center_freq = hz - off
        x = self._sdr.read_samples(262144)
        n = 8192
        w = np.hanning(n)
        segs = len(x) // n
        p = np.zeros(n)
        for s in range(segs):
            seg = x[s * n:(s + 1) * n]
            p += np.abs(np.fft.fftshift(np.fft.fft((seg - seg.mean()) * w))) ** 2
        p = 10 * np.log10(p / segs + 1e-20)
        fs = self._sdr.sample_rate
        f = np.fft.fftshift(np.fft.fftfreq(n, 1 / fs)) + hz - off
        sel = np.abs(f - hz) <= span_hz / 2
        i = np.argmax(np.where(sel, p, -1e9))
        return (float(f[i]), float(p[i]), float(np.median(p)))

    def _peak_rtl_power(self, hz, span_hz):
        lo, hi = int(hz - span_hz / 2), int(hz + span_hz / 2)
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            cmd = ["rtl_power", "-d", str(self.device_index), "-f", "%d:%d:%d" % (lo, hi, int(self.rbw)),
                   "-g", "%g" % self.gain_db, "-i", "1", "-1", path]
            if self.ppm:
                cmd[1:1] = ["-p", str(self.ppm)]
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            best, vals = None, []
            with open(path, newline="") as fh:
                for row in csv.reader(fh):
                    f0, step = float(row[2]), float(row[4])
                    for k, v in enumerate(row[6:]):
                        db = float(v)
                        f = f0 + k * step
                        vals.append(db)
                        if lo <= f <= hi and (best is None or db > best[1]):
                            best = (f, db)
            vals.sort()
            return (best[0], best[1], vals[len(vals) // 2]) if best else None
        finally:
            os.remove(path)

    def verify_source(self, source, rf_hz, gain_db, alias_hz=(), spur_dbc_max=-30.0,
                      harmonic_linearity=False, span_hz=20e3):
        """Set the Pluto to rf_hz/gain_db, measure fundamental and suspects. Returns a dict."""
        st = source.set_tone(rf_hz, gain_db)
        lo, bb = st["lo"], source.bb_offset_hz
        suspects = [("lo_leak", lo), ("pluto_image", lo - bb), ("h2", 2 * rf_hz), ("h3", 3 * rf_hz)]
        suspects += [("alias_%d" % i, f) for i, f in enumerate(alias_hz)]
        fund = self.peak(rf_hz, span_hz)
        narrow = max(5 * self.rbw, 2e3)  # suspects are measured in a narrow span so the tone itself is not counted
        out = {"rf_hz": rf_hz, "gain_db": gain_db, "fund_measured": fund is not None, "components": []}
        if fund is None:
            out.update(clean=None, reason="fundamental outside RTL range %s" % (self.range_hz,))
            return out
        out["fund_hz"], out["fund_db"], out["floor_db"] = fund
        out["freq_error_ppm"] = (fund[0] - rf_hz) / rf_hz * 1e6
        out["sideband_ok"] = abs(fund[0] - rf_hz) < max(5 * self.rbw, 25e-6 * rf_hz)
        worst, unmeasured = -999.0, []
        k = 1 + out["freq_error_ppm"] * 1e-6  # look where the error of the measured tone says they are
        for name, f in suspects:
            f = f * k
            if abs(f - rf_hz) < 2 * narrow:
                continue  # too close to the fundamental to separate
            pk = self.peak(f, narrow)
            if pk is None:
                unmeasured.append(name)
                out["components"].append({"name": name, "hz": f, "dbc": None, "measured": False})
                continue
            dbc = pk[1] - fund[1]
            above_floor = pk[1] - pk[2]
            comp = {"name": name, "hz": f, "dbc": round(dbc, 2), "above_floor_db": round(above_floor, 2),
                    "measured": True}
            if above_floor < 6.0:
                # nothing visible: the true level is somewhere below the floor, so only an upper bound
                dbc = pk[2] + 6.0 - fund[1]
                comp.update(dbc=None, dbc_upper_bound=round(dbc, 2))
            if harmonic_linearity and name in ("h2", "h3") and above_floor > 6:
                source.set_gain(gain_db - 10)
                pk2 = self.peak(f, narrow)
                source.set_gain(gain_db)
                drop = pk[1] - pk2[1]
                comp["drop_for_10db"] = round(drop, 2)
                comp["origin"] = "source" if drop < 15 else "rtl_internal"
                if comp["origin"] == "rtl_internal":
                    dbc = -999.0
            out["components"].append(comp)
            worst = max(worst, dbc)
        # 10 dB step check of the source itself (used to grade the DUT's attenuation check)
        source.set_gain(gain_db - 10)
        f10 = self.peak(rf_hz, span_hz)
        source.set_gain(gain_db)
        out["source_step_10db_measured"] = round(fund[1] - f10[1], 2) if f10 else None
        out["worst_dbc"] = round(worst, 2)
        out["unmeasured"] = unmeasured
        out["clean"] = bool(out["sideband_ok"] and worst <= spur_dbc_max)
        bounds_only = [c for c in out["components"] if c.get("dbc") is None and c.get("dbc_upper_bound") is not None]
        if out["sideband_ok"] and worst > spur_dbc_max and bounds_only and all(
                c.get("dbc") is None or c["dbc"] <= spur_dbc_max for c in out["components"]):
            out["clean"] = None
            out["reason"] = ("RTL dynamic range too small: floor only %.1f dB below the tone; raise "
                             "rtl.check_tx_gain_db or lower the RTL path loss" % (fund[1] - fund[2]))
            return out
        if not out["sideband_ok"]:
            out["reason"] = "tone not at LO+offset: check DDS sideband (dds_invert_q) or ppm"
        elif worst > spur_dbc_max:
            out["reason"] = "spur %.1f dBc above limit %.1f" % (worst, spur_dbc_max)
        return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--backend", default="auto", choices=["auto", "pyrtlsdr", "rtl_power", "sim"])
    ap.add_argument("--freq", type=float, required=True, help="tone frequency in Hz")
    ap.add_argument("--gain", type=float, default=-50.0, help="Pluto hardwaregain for the test")
    ap.add_argument("--rtl-gain", type=float, default=20.0)
    ap.add_argument("--uri", default="ip:192.168.2.1")
    ap.add_argument("--fixed-atten-db", type=float)
    ap.add_argument("--peak-only", action="store_true", help="just report the strongest bin near --freq")
    a = ap.parse_args(argv)
    if a.sim:
        from sim import SimBench
        bench = SimBench()
        rtl = RtlReference("sim", a.rtl_gain, sim_bench=bench)
    else:
        bench = None
        rtl = RtlReference(a.backend, a.rtl_gain)
    if a.peak_only:
        print(json.dumps({"backend": rtl.backend, "peak": rtl.peak(a.freq)}, indent=2)); return 0
    from pluto_source import PlutoSource
    src = PlutoSource(a.uri, "sim" if a.sim else "auto", sim_bench=bench, fixed_atten_db=a.fixed_atten_db)
    try:
        res = rtl.verify_source(src, a.freq, a.gain, harmonic_linearity=True)
    finally:
        src.disable(); rtl.close()
    print(json.dumps({"backend": rtl.backend, "note": rtl.note, **res}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
