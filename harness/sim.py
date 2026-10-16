# SPDX-License-Identifier: GPL-3.0-only
# Part of the SX1262-SDR bench harness. Credits: see harness/README.md.
"""Simulated bench: Pluto source, RTL-SDR reference and DUT on one shared model.

Every number in this file is a SIMULATION parameter, chosen only so the harness can
run end to end without hardware. None of it is a measurement or a datasheet value,
except where a comment cites the lr2021-sdr research README the shape was copied from.
"""
from __future__ import annotations

import math
import random

SX_PLL_LOCK_ERR = 0x0040  # SX126x GetDeviceErrors bit 6 (PLL lock); used only by the sim


class SimBench:
    def __init__(self, seed: int = 1234, chip: str = "SX1262", pluto_ref_dbm: float = 0.0,
                 path_loss_db: float = 46.0, rtl_path_loss_db: float = 46.0,
                 pluto_range_hz=(325e6, 3.8e9)):
        self.rng = random.Random(seed)
        self.chip = chip.upper()
        self.pluto_ref_dbm = pluto_ref_dbm          # sim: Pluto output at 0 dB hardwaregain
        self.path_loss_db = path_loss_db            # sim: fixed attenuator + filter + cables
        self.rtl_path_loss_db = rtl_path_loss_db
        self.pluto_range_hz = pluto_range_hz        # sim: "stock" range unless overridden
        self.step_atten_db = 0.0                    # manual step attenuator (sim keeps it at 0)
        self.terminated = False                     # 50 ohm terminator on DUT input
        self.pluto = {"enabled": False, "lo": 0.0, "tones": [], "gain": -89.75}
        self.ppm = {"pluto": -1.2, "dut": 2.0, "rtl": 3.5}
        self.pluto_dbc = {"lo_leak": -45.0, "image": -40.0, "h2": -38.0, "h3": -48.0}
        self.bad_image_band = (1.25e9, 1.35e9)      # sim: Pluto image only -20 dBc here (so one RTL check fails)
        self.comb_step = 40e6                       # board 40 MHz comb (sx1262-range README:66-71)
        self.comb_dbm = -112.0
        self.extra_spurs = [(433.94e6, -100.0)]      # sim: a board spur on top of the 433.92 MHz test tone
        if self.chip == "SX1262":
            self.dead = [(0, 36.9e6), (1448e6, 2623e6), (3495e6, 6e9)]  # shape from sx1262-range README:23-25
            self.irr_db = 30.0
            self.rssi_floor_dbm = -118.0
        else:
            self.dead = [(2741e6, 6e9)]
            self.irr_db = 40.0
        self.lr_floor_dbm_bin = -140.0
        self.lr_uncal_offset = 160.0                # sim: digital dB = dBm + offset
        self.rtl_floor_dbm_bin = -125.0
        self.rtl_range = (24e6, 1766e6)

    # ------------------------------------------------------------- source --
    def pluto_components(self):
        p = self.pluto
        if not p["enabled"]:
            return []
        k = 1 + self.ppm["pluto"] * 1e-6
        lo = p["lo"] * k
        p0 = self.pluto_ref_dbm + p["gain"]
        out = []
        for bb, sdb in p["tones"]:
            f = lo + bb * k
            img = self.pluto_dbc["image"]
            if self.bad_image_band[0] <= f <= self.bad_image_band[1]:
                img = -20.0
            out += [("tone", f, p0 + sdb), ("pluto_image", lo - bb * k, p0 + sdb + img),
                    ("h2", 2 * f, p0 + sdb + self.pluto_dbc["h2"]),
                    ("h3", 3 * f, p0 + sdb + self.pluto_dbc["h3"])]
        out.append(("lo_leak", lo, p0 + self.pluto_dbc["lo_leak"]))
        return out

    def at_dut(self):
        if self.terminated:
            return []
        return [(n, f, pw - self.path_loss_db - self.step_atten_db) for n, f, pw in self.pluto_components()]

    def at_rtl(self):
        return [(n, f, pw - self.rtl_path_loss_db) for n, f, pw in self.pluto_components()]

    def locked(self, hz):
        return not any(a <= hz <= b for a, b in self.dead)

    def _resp_db(self, hz):
        # sim: gentle roll-off away from the 868/915 MHz match
        return -min(15.0, abs(hz - 900e6) / 100e6)

    def _comb(self, lo_hz, half):
        k0 = math.ceil((lo_hz - half) / self.comb_step)
        k1 = math.floor((lo_hz + half) / self.comb_step)
        out = [("comb", k * self.comb_step, self.comb_dbm) for k in range(k0, k1 + 1)]
        return out + [("comb", f, p) for f, p in self.extra_spurs if abs(f - lo_hz) <= half]

    # ---------------------------------------------------- LR2021 lrprobe --
    def lr_spectrum(self, tune_hz, rate, gain=9):
        """Return dict like probe_report(): floor (digital dB), lines [(off_hz, dB over floor)]."""
        if not self.locked(tune_hz):
            return None
        lo = tune_hz * (1 + self.ppm["dut"] * 1e-6)
        half = rate / 2 * 0.9
        rbw = rate / 1024
        lines = []
        for n, f, pw in self.at_dut() + self._comb(lo, half):
            off = f - lo
            if abs(off) < half:
                pw_in = pw + (self._resp_db(tune_hz) if n != "comb" else 0)
                lines.append((off, pw_in))
                lines.append((-off, pw_in - self.irr_db))
        floor = self.lr_floor_dbm_bin
        peaks = []
        for off, pw in sorted(lines, key=lambda x: -x[1]):
            if abs(off) < 3 * rbw:
                continue
            if any(abs(off - o) < 4 * rbw for o, _ in peaks):
                continue
            peaks.append((off, pw))
        out = [(round(o / rbw) * rbw, max(pw - floor, 0.0) + self.rng.gauss(0, 0.3)) for o, pw in peaks]
        while len(out) < 3:  # noise maxima of an averaged spectrum
            out.append((self.rng.uniform(-half, half), self.rng.uniform(4.0, 7.0)))
        out = sorted(out, key=lambda x: -x[1])[:3]
        floor_db = floor + self.lr_uncal_offset + self.rng.gauss(0, 0.2)
        return {"floor_db": floor_db, "peaks": out, "rate": rate, "rbw": rbw}

    # --------------------------------------------------- SX1262 sxprobe --
    def sx_rssi(self, khz, bw_hz):
        f0 = khz * 1000 * (1 + self.ppm["dut"] * 1e-6)
        if not self.locked(khz * 1000):
            return None
        tot = 10 ** (self.rssi_floor_dbm / 10)
        sigma = bw_hz / 2.355
        for n, f, pw in self.at_dut() + self._comb(f0, 4 * bw_hz):
            d = f - f0
            if abs(d) < 4 * bw_hz:
                g = math.exp(-0.5 * (d / sigma) ** 2)
                tot += 10 ** ((pw + (self._resp_db(khz * 1000) if n != "comb" else 0)) / 10) * g
        return 10 * math.log10(tot)

    # ------------------------------------------------------------- RTL --
    def rtl_level(self, hz, rbw=1000.0):
        """dBFS-like level (sim offset +10) at hz; None if outside RTL tuning range."""
        if not (self.rtl_range[0] <= hz <= self.rtl_range[1]):
            return None
        k = 1 + self.ppm["rtl"] * 1e-6
        tot = 10 ** (self.rtl_floor_dbm_bin / 10)
        for n, f, pw in self.at_rtl():
            if abs(f / k - hz) < rbw * 1.5:
                tot += 10 ** (pw / 10)
        return 10 * math.log10(tot) + 10.0 + self.rng.gauss(0, 0.3)

    def rtl_peak(self, hz, span, rbw=1000.0):
        """(peak_hz, peak_db, floor_db) in [hz-span/2, hz+span/2], RTL-frequency-referenced."""
        if not (self.rtl_range[0] <= hz <= self.rtl_range[1]):
            return None
        k = 1 + self.ppm["rtl"] * 1e-6
        best = None
        for n, f, pw in self.at_rtl():
            fr = f / k
            if abs(fr - hz) <= span / 2 and (best is None or pw > best[1]):
                best = (fr, pw)
        floor = self.rtl_floor_dbm_bin + 10.0
        if best is None:
            return (hz, floor + self.rng.uniform(3, 5), floor)
        return (round(best[0] / rbw) * rbw, max(best[1] + 10.0, floor) + self.rng.gauss(0, 0.3), floor)
