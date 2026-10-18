# SPDX-License-Identifier: GPL-3.0-only
# Part of the SX1262-SDR bench harness. Credits: see harness/README.md.
"""Bench sweep for SX1262 / LR2021 receive tests (the section 8 test plan of
harness/TESTING-NOTES.md).

Phases
  0  detect: Pluto TX range (read from the radio), DUT profile range, RTL range
  1  source check (RTL-SDR): fundamental, LO leak, Pluto image, 2f/3f, DUT-image alias, 10 dB step
  2  spur map with the DUT input terminated (50 ohm), Pluto off
  3  randomised (frequency x rep) list; per item:
       base    tone at F+delta, DUT tuned to F         -> SNR, noise floor, ppm, image rejection
       shift   tone at F+delta+shift                   -> response must move +shift  (check 1)
       retune  DUT tuned to F+retune                   -> response must move -retune (check 2)
       atten   tone 10 dB lower                        -> response must drop 10 dB   (check 3)
       rtl     phase-1 result for F                    -> source clean               (check 4)
       mds     step the source down until SNR < threshold
       imd     optional two-tone third-order products
  4  summary: CSV + JSON metadata in results/<run>/, then plot_results.py

Usage
  python run_sweep.py --sim                      # whole sweep against the simulator
  python run_sweep.py --config my.json --port COM39 --fixed-atten-db 40
"""
from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import json
import os
import platform
import random
import statistics
import hashlib
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dut_serial import Dut, load_profiles, heltec_identity_matches  # noqa: E402
from pluto_source import PlutoSource  # noqa: E402
from rtl_reference import RtlReference  # noqa: E402

MEAS_FIELDS = ["run_id", "order", "rep", "freq_hz", "tune_hz", "source_hz", "status", "fail_reasons", "locked",
               "detected", "snr_db", "level_db", "noise_db", "units", "rbw_hz", "offset_hz", "expected_offset_hz",
               "ppm_dut_vs_pluto", "image_rejection_db", "image_lower_bound", "shift_moved_hz", "shift_ok",
               "retune_moved_hz", "retune_ok", "atten_drop_db", "atten_expected_db", "atten_ok", "rtl_clean",
               "rtl_worst_dbc", "spur_conflict", "tx_gain_db", "input_dbm", "mds_tx_gain_db", "mds_input_dbm",
               "mds_note", "source_off_snr_db", "source_off_ok", "capture_ok", "rx_note", "imd_dbc", "imd_lower_bound", "timestamp"]


def deep_update(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            deep_update(a[k], v)
        else:
            a[k] = v
    return a


def load_config(path=None, extra=None):
    with open(os.path.join(HERE, "config", "default.json")) as fh:
        cfg = json.load(fh)
    if path:
        with open(path) as fh:
            deep_update(cfg, json.load(fh))
    if extra:
        deep_update(cfg, extra)
    return cfg


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def git_commit():
    try:
        return subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def evaluate(base, shift, retune, att, rtl_clean, p, shift_hz, retune_hz, atten_expected_db, tol_hz,
             spur_conflict, unverified_as="unverified", source_off=None):
    """Pure pass/fail logic. Returns (status, reasons, checks dict)."""
    reasons, checks = [], {}

    def det(m):
        return bool(m and m.get("detected"))

    if not base.get("locked", True):
        reasons.append("no_lock")
    if base.get("raw_ok") is False:
        reasons.append("invalid_probe")
    if not det(base):
        reasons.append("no_response")
    snr = base.get("snr_db")
    if snr is None or snr < p["snr_min_db"]:
        reasons.append("snr_below_%g" % p["snr_min_db"])
    # 1 source shift: response moves the same way, same level
    if det(base) and det(shift):
        moved = shift["offset_hz"] - base["offset_hz"]
        ok = abs(moved - shift_hz) <= tol_hz and abs(shift["level_db"] - base["level_db"]) <= p["level_tol_db"]
        checks["source_shift"] = {"pass": ok, "moved_hz": moved}
    else:
        checks["source_shift"] = {"pass": False, "moved_hz": None}
    # 2 retune: response moves the opposite way
    if det(base) and det(retune):
        moved = retune["offset_hz"] - base["offset_hz"]
        checks["retune"] = {"pass": abs(moved + retune_hz) <= tol_hz, "moved_hz": moved}
    else:
        checks["retune"] = {"pass": False, "moved_hz": None}
    # 3 attenuation: 10 dB less in, 10 dB less out
    if det(base) and det(att):
        drop = base["level_db"] - att["level_db"]
        checks["atten_10db"] = {"pass": abs(drop - atten_expected_db) <= p["atten_tol_db"], "drop_db": drop}
    elif det(base) and (snr or 0) < atten_expected_db + p["snr_min_db"]:
        checks["atten_10db"] = {"pass": False, "drop_db": None, "why": "base SNR too low to see a 10 dB step"}
    else:
        checks["atten_10db"] = {"pass": False, "drop_db": None}
    # 4 RTL: source clean at the suspect frequencies
    checks["rtl_clean"] = {"pass": rtl_clean is True, "value": rtl_clean}
    # A paired source-OFF capture is an independent negative control for RSSI and IQ.
    if source_off is None:
        checks["source_off"] = {"pass": False, "value": "not_run"}
    else:
        off_snr = source_off.get("snr_db")
        quiet = (not source_off.get("detected") or
                 (off_snr is not None and off_snr < p["snr_min_db"]))
        checks["source_off"] = {
            "pass": bool(source_off.get("raw_ok") and source_off.get("locked", True) and quiet),
            "snr_db": off_snr, "value": "quiet" if quiet else "residual_signal"}
    unverified = False
    for name in p["require_checks"]:
        c = checks.get(name)
        if c and not c["pass"]:
            if name == "source_off" and source_off is None:
                unverified = True
                continue
            if name == "rtl_clean" and rtl_clean is None and unverified_as != "fail":
                if unverified_as == "unverified":
                    unverified = True
                continue
            reasons.append(name)
    if spur_conflict and p.get("fail_on_spur_conflict", True):
        reasons.append("spur_conflict")
    if reasons:
        return "FAIL", reasons, checks
    return ("UNVERIFIED" if unverified else "PASS"), (["rtl_unverified"] if unverified else []), checks


class Runner:
    def __init__(self, cfg, sim=False, out_root=None, assume_yes=False, sim_pluto_range=None, seed=None):
        self.cfg = cfg
        self.sim = sim
        self.yes = assume_yes or sim
        sw = cfg["sweep"]
        self.seed = seed if seed is not None else (sw["seed"] if sw["seed"] is not None else random.SystemRandom().randrange(1 << 31))
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.run_id = "%s_%s%s" % (stamp, cfg["label"], "_SIM" if sim else "")
        self.out = os.path.join(out_root or os.path.join(HERE, "results"), self.run_id)
        os.makedirs(self.out, exist_ok=False)
        self._logf = open(os.path.join(self.out, "run.log"), "w", encoding="utf-8")
        # Required by project contract: persist a second log in the launch directory.
        self._cwd_logf = open(os.path.join(os.getcwd(), "SX1262-SDR.log"), "a", encoding="utf-8")
        self.warnings = []
        prof = load_profiles()[cfg["dut"]["profile"]]
        # Reject a placeholder before opening a real Pluto RF backend.
        if not sim and prof.get("todo"):
            self._logf.close()
            self._cwd_logf.close()
            raise RuntimeError("Heltec receiver profile is a TODO; no Pluto access is permitted")
        self.bench = None
        if sim:
            from sim import SimBench
            rng = sim_pluto_range or (325e6, 3.8e9)
            self.bench = SimBench(seed=self.seed, chip=prof["chip"],
                                  pluto_ref_dbm=cfg["pluto"]["ref_dbm_at_0db_gain"] if cfg["pluto"]["ref_dbm_at_0db_gain"] is not None else 0.0,
                                  pluto_range_hz=rng)
        if self.bench is not None and self.total_loss_db() is not None:
            self.bench.path_loss_db = self.total_loss_db()
        pc = cfg["pluto"]
        self.src = PlutoSource(pc["uri"], "sim" if sim else pc["backend"], self.bench,
                               fixed_atten_db=cfg["path"]["fixed_atten_db"], min_fixed_atten_db=pc["min_fixed_atten_db"],
                               max_gain_db=pc["max_gain_db"], bb_offset_hz=pc["bb_offset_hz"],
                               dds_invert_q=pc["dds_invert_q"])
        self.rtl = None
        if cfg["rtl"]["enabled"]:
            rc = cfg["rtl"]
            try:
                self.rtl = RtlReference("sim" if sim else rc["backend"], rc["gain_db"], rc["ppm"], self.bench,
                                        tuple(rc["range_hz"]), rc["rbw_hz"])
                if self.rtl.note:
                    self.warn(self.rtl.note)
            except Exception as e:  # noqa: BLE001
                self.warn("RTL reference unavailable (%s): rtl_clean will be UNVERIFIED" % e)
        dc = cfg["dut"]
        try:
            self.dut = Dut(dc["profile"], dc["port"], dc["serial_number"], self.bench,
                           overrides=dc["overrides"], log=self.log_raw)
        except BaseException:
            # If __init__ raises, main() has no fully constructed Runner to close.
            self.src.disable()
            if self.rtl:
                self.rtl.close()
            self._logf.close()
            self._cwd_logf.close()
            raise
        d = self.dut.params
        # RSSI sweeps do NOT independently test LO retuning: a shifted nominal
        # centre with the same absolute scan steps produces a tautological offset.
        # Use source-shift, attenuation and paired source-OFF instead.
        required = self.cfg["pass"]["require_checks"]
        if self.dut.kind == "rssi_sweep":
            self.cfg["pass"]["require_checks"] = list(self.cfg["pass"].get(
                "rssi_require_checks", ["source_shift", "atten_10db", "source_off", "rtl_clean"]))
        elif "source_off" not in required:
            required.append("source_off")
        if self.dut.kind == "iq_peaks":
            self.rbw = 4 * d.get("bw", 31250) / 1024.0
            self.nyq = 2 * d.get("bw", 31250)
        elif self.dut.kind == "iq_dump":
            self.rbw = d.get("rate", 125000) / 1024.0
            self.nyq = d.get("rate", 125000) / 2
        else:
            self.rbw = d.get("step_hz", 1000)
            self.nyq = None
        self.tol = sw["offset_tol_hz"] or (max(2 * self.rbw, 300.0) if self.dut.kind != "rssi_sweep" else 1.5 * self.rbw)

    def close(self):
        # Must run on *every* exception, including failures before measurements.csv.
        try:
            if hasattr(self, "src"):
                self.src.disable()
        finally:
            for dev in (getattr(self, "dut", None), getattr(self, "rtl", None)):
                if dev is not None:
                    try:
                        dev.close()
                    except Exception as exc:
                        print("cleanup warning: %s" % exc, file=sys.stderr)
            for fh in (getattr(self, "_logf", None), getattr(self, "_cwd_logf", None)):
                if fh is not None and not fh.closed:
                    fh.close()

    # ------------------------------------------------------------ utils --
    def log(self, msg):
        line = "[%s] %s" % (dt.datetime.now().strftime("%H:%M:%S"), msg)
        print(line, flush=True)
        for fh in (self._logf, self._cwd_logf):
            fh.write(line + "\n")
            fh.flush()

    def log_raw(self, txt):
        for fh in (self._logf, self._cwd_logf):
            fh.write(txt + ("\n" if not txt.endswith("\n") else ""))
            fh.flush()

    def warn(self, msg):
        self.warnings.append(msg)
        self.log("WARNING: " + msg)

    def prompt(self, msg):
        self.log("ACTION: " + msg)
        if not self.yes:
            input("    press Enter when done (Ctrl+C aborts) ")

    def ask(self, key, msg):
        if self.cfg["meta"].get(key) is None and not self.yes:
            v = input("%s (blank = unknown): " % msg).strip()
            self.cfg["meta"][key] = v or None

    def total_loss_db(self):
        pth = self.cfg["path"]
        parts = [pth["fixed_atten_db"], pth.get("filter_loss_db"), pth["cable_loss_db"], pth["step_atten_db"]]
        if self.cfg["rtl"]["path"] == "splitter":
            parts.append(pth["splitter_loss_db"])
        if any(x is None for x in parts):
            return None
        return float(sum(parts))

    def input_dbm(self, gain_db):
        ref, loss = self.cfg["pluto"]["ref_dbm_at_0db_gain"], self.total_loss_db()
        if self.sim and loss is None:
            loss = self.bench.path_loss_db
        return None if ref is None or loss is None else round(ref + gain_db - loss, 2)

    def window(self, f):
        d = abs(self.cfg["sweep"]["delta_hz"])
        return min(self.cfg["sweep"]["ppm_window"] * 1e-6 * f + 2 * self.rbw, 0.8 * d)

    def measure(self, tune, src_hz, gain, expect, window, extra=()):
        self.src.set_tone(src_hz, gain, extra)
        time.sleep(0 if self.sim else self.cfg["sweep"]["settle_s"])
        return self.dut.measure(tune, expect, window)

    # ----------------------------------------------------------- phases --
    def phase0(self):
        sw = self.cfg["sweep"]
        freqs, skipped = [], []
        d, s = sw["delta_hz"], sw["shift_hz"]
        if self.nyq and abs(d) + abs(s) + self.tol >= self.nyq * 0.9:
            raise SystemExit("delta+shift %.0f Hz is too close to the DUT Nyquist %.0f Hz" % (abs(d) + abs(s), self.nyq))
        for mhz in sw["frequencies_mhz"]:
            f = mhz * 1e6
            if not self.src.covers(f + d) or not self.src.covers(f + d + s):
                skipped.append({"freq_hz": f, "reason": "outside detected Pluto TX range %s" % (self.src.range_hz,)})
            elif not self.dut.covers(f) or not self.dut.covers(f + sw["retune_hz"]):
                skipped.append({"freq_hz": f, "reason": "outside DUT profile range"})
            else:
                freqs.append(f)
        for sk in skipped:
            self.warn("skip %.3f MHz: %s" % (sk["freq_hz"] / 1e6, sk["reason"]))
        self.log("Pluto: %s, TX range %s" % (self.src.info.get("hw_model"), self.src.range_hz))
        return freqs, skipped

    def phase1(self, freqs):
        res = {}
        if not self.rtl:
            return res
        rc, sw = self.cfg["rtl"], self.cfg["sweep"]
        self.prompt("Connect the RTL-SDR reference path (Pluto -> filter -> fixed attenuator -> RTL). "
                    "Never connect the Pluto to the RTL without the attenuator.")
        g0 = rc.get("check_tx_gain_db", self.cfg["pluto"]["tx_gain_db"])
        for f in freqs:
            src_hz = f + sw["delta_hz"]
            aliases = [f - sw["delta_hz"]]  # where the DUT's own image would sit
            r = self.rtl.verify_source(self.src, src_hz, g0, aliases, rc["spur_dbc_max"], rc["harmonic_linearity"],
                                       span_hz=max(20e3, 4 * rc["rbw_hz"]))
            self.src.disable()
            res[f] = r
            self.log("RTL %.3f MHz: clean=%s worst=%s dBc step10=%s unmeasured=%s %s" % (
                f / 1e6, r.get("clean"), r.get("worst_dbc"), r.get("source_step_10db_measured"),
                ",".join(r.get("unmeasured", [])), r.get("reason", "")))
        with open(os.path.join(self.out, "source_check.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["freq_hz", "source_hz", "clean", "worst_dbc", "fund_db", "floor_db", "freq_error_ppm",
                        "sideband_ok", "step_10db_measured", "component", "component_hz", "dbc", "measured", "origin"])
            for f, r in res.items():
                for c in r.get("components", []) or [{}]:
                    w.writerow([f, r["rf_hz"], r.get("clean"), r.get("worst_dbc"), r.get("fund_db"), r.get("floor_db"),
                                r.get("freq_error_ppm"), r.get("sideband_ok"), r.get("source_step_10db_measured"),
                                c.get("name"), c.get("hz"), c.get("dbc"), c.get("measured"), c.get("origin")])
        return res

    def phase2(self, freqs):
        spurs = {}
        if not self.cfg["sweep"]["terminated_spur_map"]:
            return spurs
        self.src.disable()
        self.prompt("Fit a 50 ohm terminator on the DUT input (Pluto disconnected).")
        if self.bench:
            self.bench.terminated = True
        thr = self.cfg["sweep"]["spur_threshold_db"]
        rows = []
        for f in freqs:
            for tune in (f, f + self.cfg["sweep"]["retune_hz"]):
                m, sp = self.dut.spur_scan(tune, thr)
                spurs.setdefault(f, []).extend([(tune - f + o, d) for o, d in sp])
                rows.append([f, tune, m.get("noise_db"), m.get("units"), m.get("locked"),
                             ";".join("%+.0f:%.1f" % (o, d) for o, d in sp)])
            self.log("spur map %.3f MHz: floor=%s %s spurs=%s" % (f / 1e6, rows[-2][2], rows[-2][3], rows[-2][5] or "-"))
        if self.bench:
            self.bench.terminated = False
        with open(os.path.join(self.out, "spur_map.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["freq_hz", "tune_hz", "noise_db", "units", "locked", "spurs_offset_hz:db_over_floor"])
            w.writerows(rows)
        return spurs

    def spur_conflict(self, f, spurs):
        sw = self.cfg["sweep"]
        d, s, r = sw["delta_hz"], sw["shift_hz"], sw["retune_hz"]
        # offsets relative to F where a real response is expected (tune F and tune F+r)
        expect = [d, d + s]  # spur offsets are stored relative to absolute F, not the nominal sweep centre
        # a spur anywhere the base search could pick it up (ppm window) is a confound
        win = max(self.window(f), 2 * self.tol)
        return any(abs(o - e) <= win for o, _ in spurs.get(f, []) for e in expect)

    def mds(self, f, src_hz, g0, base_offset):
        sw, p = self.cfg["sweep"], self.cfg["pass"]
        from pluto_source import GAIN_MIN_DB

        def ok(g):
            m = self.measure(f, src_hz, g, base_offset, 3 * self.tol)
            return m.get("detected") and (m.get("snr_db") or 0) >= p["snr_min_db"], m

        g, good = g0, None
        while g >= GAIN_MIN_DB:
            passed, _ = ok(g)
            if not passed:
                break
            good = g
            g -= sw["mds"]["coarse_step_db"]
        if good is None:
            return None, "no detection at start level"
        g = good - sw["mds"]["fine_step_db"]
        while g > good - sw["mds"]["coarse_step_db"] and g >= GAIN_MIN_DB:
            passed, _ = ok(g)
            if not passed:
                break
            good = g
            g -= sw["mds"]["fine_step_db"]
        note = "limited by Pluto minimum gain: add step attenuation" if good - sw["mds"]["fine_step_db"] < GAIN_MIN_DB else ""
        return good, note

    def imd(self, f, g0, o0):
        sw = self.cfg["sweep"]
        if self.dut.kind == "rssi_sweep":
            return None, None
        d, sp = sw["delta_hz"], sw["imd"]["tone_spacing_hz"]
        self.src.set_tone(f + d, g0, (sp,))
        m = self.dut.measure(f, o0, 3 * self.tol, image=False)
        d = o0  # positions relative to where the base tone was actually seen
        if not m.get("detected"):
            return None, None
        im = [Dut._pick(m["peaks"], e, 3 * self.tol) for e in (d - sp, d + 2 * sp)]
        im = [x for x in im if x]
        if im:
            return round(m["snr_db"] - max(x[1] for x in im), 2), False
        others = [x[1] for x in m["peaks"] if abs(x[0] - d) > 3 * self.tol and abs(x[0] - d - sp) > 3 * self.tol]
        return round(m["snr_db"] - (min(others) if others else 0.0), 2), True

    def item(self, order, rep, f, rtl_res, spurs):
        sw, p = self.cfg["sweep"], self.cfg["pass"]
        d, s, r, a = sw["delta_hz"], sw["shift_hz"], sw["retune_hz"], sw["atten_step_db"]
        g0 = self.cfg["pluto"]["tx_gain_db"]
        src_hz = f + d
        base = self.measure(f, src_hz, g0, d, self.window(f))
        o0 = base["offset_hz"] if base.get("detected") else d
        shift = self.measure(f, src_hz + s, g0, o0 + s, 3 * self.tol)
        retune = (None if self.dut.kind == "rssi_sweep" else
                  self.measure(f + r, src_hz, g0, o0 - r, 3 * self.tol))
        att = self.measure(f, src_hz, g0 - a, o0, 3 * self.tol)
        self.src.disable()
        source_off = self.dut.measure(f, o0, 3 * self.tol)
        rr = rtl_res.get(f, {})
        rtl_clean = rr.get("clean") if rr else None
        step = rr.get("source_step_10db_measured") if rr else None
        atten_expected = step if (step is not None and abs(step - a) <= 1.5) else a
        conflict = self.spur_conflict(f, spurs)
        status, reasons, checks = evaluate(base, shift, retune, att, rtl_clean, p, s, r, atten_expected, self.tol,
                                           conflict, p.get("unverified_rtl_counts_as", "unverified"),
                                           source_off=source_off)
        mds_g, mds_note = (None, "")
        if sw["mds"]["enabled"] and base.get("detected"):
            mds_g, mds_note = self.mds(f, src_hz, g0, o0)
        imd_v, imd_lb = (None, None)
        if sw["imd"]["enabled"]:
            imd_v, imd_lb = self.imd(f, g0, o0)
        self.src.disable()
        ppm = ((base["offset_hz"] - d) / f * 1e6) if base.get("detected") else None
        row = {"run_id": self.run_id, "order": order, "rep": rep, "freq_hz": f, "tune_hz": f, "source_hz": src_hz,
               "status": status, "fail_reasons": ";".join(reasons), "locked": base.get("locked"),
               "detected": base.get("detected"), "snr_db": _r(base.get("snr_db")), "level_db": _r(base.get("level_db")),
               "noise_db": _r(base.get("noise_db")), "units": base.get("units"), "rbw_hz": _r(base.get("rbw_hz")),
               "offset_hz": _r(base.get("offset_hz")), "expected_offset_hz": d, "ppm_dut_vs_pluto": _r(ppm, 3),
               "image_rejection_db": base.get("image_db"), "image_lower_bound": base.get("image_lower_bound"),
               "shift_moved_hz": _r(checks["source_shift"]["moved_hz"]), "shift_ok": checks["source_shift"]["pass"],
               "retune_moved_hz": _r(checks["retune"]["moved_hz"]) if retune is not None else None,
               "retune_ok": checks["retune"]["pass"] if retune is not None else None,
               "atten_drop_db": _r(checks["atten_10db"].get("drop_db")), "atten_expected_db": atten_expected,
               "atten_ok": checks["atten_10db"]["pass"], "rtl_clean": rtl_clean, "rtl_worst_dbc": rr.get("worst_dbc") if rr else None,
               "spur_conflict": conflict, "tx_gain_db": g0, "input_dbm": self.input_dbm(g0),
               "mds_tx_gain_db": mds_g, "mds_input_dbm": self.input_dbm(mds_g) if mds_g is not None else None,
               "mds_note": mds_note, "source_off_snr_db": _r(source_off.get("snr_db")),
               "source_off_ok": checks["source_off"]["pass"], "capture_ok": base.get("raw_ok"),
               "rx_note": base.get("note"), "imd_dbc": imd_v, "imd_lower_bound": imd_lb, "timestamp": now_iso()}
        self.log("#%03d rep%d %9.3f MHz %-10s snr=%s shift=%s retune=%s att=%s rtl=%s mds_gain=%s %s" % (
            order, rep, f / 1e6, status, row["snr_db"], row["shift_ok"], row["retune_ok"], row["atten_drop_db"],
            rtl_clean, mds_g, row["fail_reasons"]))
        return row

    # -------------------------------------------------------------- run --
    def run_pll_only(self):
        """RX tuning/status survey with the external source disabled throughout."""
        started = now_iso()
        info = self.dut.info()
        if not heltec_identity_matches(self.dut.p, info):
            raise RuntimeError('Heltec firmware identity mismatch')
        self.src.disable()
        if not self.sim and self.src._phy.find_channel('altvoltage1', True).attrs['powerdown'].value != '1':
            raise RuntimeError('Pluto TX OFF readback failed')
        self.log('RX-only synthesizer survey: Pluto TX OFF; no external stimulus; no receive proof')
        rows, probes = [], []
        try:
            for order, mhz in enumerate(self.cfg['sweep']['frequencies_mhz'], 1):
                hz = int(round(float(mhz) * 1e6))
                sample = self.dut.run('probe', freq_hz=hz, dwell_ms=20)
                probes.append(sample)
                if not sample.get('_done'):
                    raise RuntimeError('DUT communications lost; survey stopped')
                reasons = []
                if not sample.get('ok'): reasons.append('probe_invalid')
                if sample.get('errors', 0): reasons.append('device_errors_0x%04X' % sample['errors'])
                row = dict.fromkeys(MEAS_FIELDS)
                row.update(run_id=self.run_id, order=order, rep=1, freq_hz=hz, tune_hz=hz,
                           status='FAIL' if reasons else 'UNVERIFIED',
                           fail_reasons=';'.join(reasons or ['no_external_stimulus']),
                           level_db=sample.get('rssi_dbm'), capture_ok=bool(sample.get('ok')),
                           units='SX1262 instantaneous RSSI dBm (uncalibrated)',
                           rx_note='status=0x%02X errors=0x%04X; no lock flag or source-correlated reception'
                                   % (sample.get('status', 0), sample.get('errors', 0)), timestamp=now_iso())
                rows.append(row)
                self.log('%.3f MHz: ok=%s status=0x%02X errors=0x%04X RSSI=%s'
                         % (mhz, sample.get('ok'), sample.get('status', 0),
                            sample.get('errors', 0), sample.get('rssi_dbm')))
        finally:
            try:
                stopped = self.dut.run('stop')
                if not stopped.get('_done') or str(stopped.get('ok')) != '1':
                    raise RuntimeError('Heltec standby not confirmed')
            finally:
                self.src.disable()
        with open(os.path.join(self.out, 'measurements.csv'), 'w', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=MEAS_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        summary = self.summarise([int(round(float(f) * 1e6)) for f in self.cfg['sweep']['frequencies_mhz']], rows)
        meta = {'run_id': self.run_id, 'simulated': self.sim, 'started': started, 'finished': now_iso(),
                'mode': 'pll-only', 'direction': 'heltec-rx-source-off', 'harness_commit': git_commit(),
                'meta': self.cfg['meta'], 'path': self.cfg['path'], 'config': self.cfg,
                'dut': {'profile': self.dut.name, 'info': info}, 'pluto': self.src.describe(), 'probes': probes,
                'evidence': 'SIMULATED' if self.sim else 'COMMAND_ACCEPTED',
                'limitations': 'No external RF stimulus; clear error flags are not an independent PLL lock or receive proof; image calibration is only performed at 902-928 MHz'}
        with open(os.path.join(self.out, 'meta.json'), 'w') as fh:
            json.dump(meta, fh, indent=2, default=str)
        self.log('Survey saved: ' + self.out)
        with open(os.path.join(self.out, 'sha256.txt'), 'w') as fh:
            for name in ('meta.json', 'measurements.csv', 'summary.csv', 'run.log'):
                with open(os.path.join(self.out, name), 'rb') as evidence:
                    fh.write(hashlib.sha256(evidence.read()).hexdigest() + '  ' + name + '\n')
        return self.out, summary

    def run_nominal(self, receive_check=False):
        """Bounded unfiltered RSSI checks; never a sensitivity or source-purity claim."""
        started = now_iso()
        info = self.dut.info()
        if not heltec_identity_matches(self.dut.p, info):
            raise RuntimeError('Heltec identity mismatch; no RF enabled')
        self.src.disable()
        if not self.sim and self.src._phy.find_channel('altvoltage1', True).attrs['powerdown'].value != '1':
            raise RuntimeError('Pluto TX OFF readback failed before baseline')
        freqs = ([int(round(float(f) * 1e6)) for f in self.cfg['sweep']['frequencies_mhz']]
                 if receive_check else [915000000])
        tone_offset = 1000 if str(self.dut.params.get('probe_mode')).startswith('gfsk') else 20000
        if not freqs or len(freqs) > 20:
            raise ValueError('Bounded receive check requires 1..20 frequencies')
        offsets = self.cfg['sweep'].get('rx_offsets_hz', [0]) if receive_check else [0]
        offset_scan = offsets != [0]
        fixed_rx = self.cfg['sweep'].get('fixed_rx_hz')
        if fixed_rx is not None and (not receive_check or offset_scan or
                not str(self.dut.params.get('probe_mode')).startswith('gfsk') or
                not 37000000 <= fixed_rx <= 340000000 or
                any(not 37000000 <= hz + tone_offset <= 340000000 or
                    abs(hz + tone_offset - fixed_rx) > 400000 for hz in freqs)):
            raise ValueError('Fixed RX check requires GFSK receive-check, no RX offsets, source/RX <=340 MHz within 400 kHz')
        if (not offsets or len(offsets) > 19 or any(not -400000 <= o <= 400000 for o in offsets) or
                (offset_scan and (len(freqs) > 3 or max(freqs) > 340000000 or
                                  not str(self.dut.params.get('probe_mode')).startswith('gfsk')))):
            raise ValueError('Lower offset check requires GFSK, <=3 sources <=340 MHz, <=19 offsets within +/-400 kHz')
        for hz in freqs:
            if not 37000000 <= hz <= 3000000000 or not self.src.covers(min(hz + tone_offset, 3000000000)):
                raise ValueError('Receive check outside detected source range or 3 GHz attenuator rating: %s' % hz)
        rows, raw_samples, failed_freqs = [], [], set()
        gains = (-60.0,) if offset_scan or fixed_rx is not None else (-80.0, -70.0, -60.0)
        items = [(hz, gain, offset) for hz in freqs for gain in gains for offset in offsets]
        try:
            for order, (hz, gain, offset) in enumerate(items, 1):
                if hz in failed_freqs:
                    continue
                source_hz = min(hz + tone_offset, 3000000000)
                tune_hz = fixed_rx if fixed_rx is not None else hz + offset
                off = self.dut.run('probe', freq_hz=tune_hz, dwell_ms=20)
                if not off.get('_done') or not off.get('ok') or off.get('errors'):
                    if receive_check and off.get('_done') and off.get('errors'):
                        failed_freqs.add(hz)
                        row = dict.fromkeys(MEAS_FIELDS)
                        row.update(run_id=self.run_id, order=order, rep=1, freq_hz=hz, tune_hz=tune_hz,
                                   status='FAIL', fail_reasons='device_errors_no_source_enabled',
                                   capture_ok=False, rx_note=str(off), timestamp=now_iso())
                        rows.append(row)
                        raw_samples.append({'frequency_hz': hz, 'before': off, 'source_enabled': False})
                        self.log('%.3f MHz: device errors before TX; source not enabled' % (hz / 1e6))
                        continue
                    raise RuntimeError('Invalid source-OFF RX probe; refusing TX')
                self.log('Pluto source ON: %d Hz, hardwaregain=%.1f dB, fixed pad=30 dB' % (source_hz, gain))
                try:
                    source_state = self.src.set_tone(source_hz, gain)
                    self.log('Pluto source state: %s' % json.dumps(source_state, default=str))
                    on = self.dut.run('probe', freq_hz=tune_hz, dwell_ms=20)
                finally:
                    self.src.disable()
                    self.log('Pluto source OFF requested')
                if not self.sim and self.src._phy.find_channel('altvoltage1', True).attrs['powerdown'].value != '1':
                    raise RuntimeError('Pluto TX OFF unconfirmed; independently check RF OFF')
                after = self.dut.run('probe', freq_hz=tune_hz, dwell_ms=20)
                raw_samples.append({'frequency_hz': hz, 'tune_hz': tune_hz, 'rx_offset_hz': tune_hz - hz,
                                    'source_state': source_state,
                                    'gain_db': gain, 'before': off, 'on': on, 'after': after})
                if not all(x.get('_done') and x.get('ok') and x.get('errors') == 0
                           for x in (off, on, after)):
                    raise RuntimeError('Invalid RX/status response; stopped nominal test')
                delta = on['rssi_dbm'] - off['rssi_dbm']
                quiet = abs(after['rssi_dbm'] - off['rssi_dbm']) <= 3
                row = dict.fromkeys(MEAS_FIELDS)
                row.update(run_id=self.run_id, order=order, rep=1, freq_hz=hz,
                           tune_hz=tune_hz, source_hz=source_hz, tx_gain_db=gain,
                           status='UNVERIFIED', fail_reasons='unfiltered_receive_check' if receive_check else 'unfiltered_nominal_baseline',
                           level_db=on['rssi_dbm'], noise_db=off['rssi_dbm'],
                           units='SX1262 instantaneous RSSI dBm (uncalibrated)',
                           detected=delta >= 3, source_off_ok=quiet, capture_ok=True,
                           rx_note='ON-OFF delta=%.1f dB; post-OFF=%.1f dBm; no source-purity verification'
                                   % (delta, after['rssi_dbm']), timestamp=now_iso())
                rows.append(row)
                self.log('%.3f MHz gain %.1f dB RXoffset %+.1f kHz: OFF %.1f, ON %.1f, post-OFF %.1f dBm RSSI; delta %.1f dB'
                         % (hz / 1e6, gain, (tune_hz - hz) / 1000, off['rssi_dbm'], on['rssi_dbm'], after['rssi_dbm'], delta))
        except BaseException as exc:
            self.log('Receive check aborted; partial evidence preserved: %s' % exc)
            with open(os.path.join(self.out, 'partial.json'), 'w') as fh:
                json.dump({'run_id': self.run_id, 'simulated': self.sim, 'status': 'aborted',
                           'started': started, 'finished': now_iso(), 'error': str(exc),
                           'dut_info': info, 'config': self.cfg, 'measurements': rows,
                           'probes': raw_samples}, fh, indent=2, default=str)
            raise
        finally:
            try:
                stopped = self.dut.run('stop')
                if not stopped.get('_done') or str(stopped.get('ok')) != '1':
                    raise RuntimeError('Heltec standby not confirmed')
            finally:
                self.src.disable()
        with open(os.path.join(self.out, 'measurements.csv'), 'w', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=MEAS_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        summary = self.summarise(freqs, rows)
        meta = {'run_id': self.run_id, 'simulated': self.sim, 'started': started, 'finished': now_iso(),
                'direction': 'pluto-tx-heltec-rx', 'mode': 'bounded-receive-check' if receive_check else 'nominal-915-only',
                'rx_offsets_hz': offsets,
                'fixed_rx_hz': fixed_rx,
                'scan_axis': 'source-frequency' if fixed_rx is not None else 'receiver-frequency',
                'harness_commit': git_commit(), 'meta': self.cfg['meta'], 'path': self.cfg['path'],
                'pluto': self.src.describe(), 'dut': {'profile': self.dut.name, 'info': info},
                'probes': raw_samples, 'config': self.cfg,
                'evidence': 'SIMULATED' if self.sim else 'RSSI_OBSERVED',
                'limitations': 'Operator-authorized SSTV pad/cable setup without source filter; uncalibrated RSSI, no independent source-purity check, frequency tracking or sensitivity claim; out-of-band image calibration not validated'}
        with open(os.path.join(self.out, 'meta.json'), 'w') as fh:
            json.dump(meta, fh, indent=2, default=str)
        self.print_summary(summary)
        with open(os.path.join(self.out, 'sha256.txt'), 'w') as fh:
            for name in ('meta.json', 'measurements.csv', 'summary.csv', 'run.log'):
                with open(os.path.join(self.out, name), 'rb') as evidence:
                    fh.write(hashlib.sha256(evidence.read()).hexdigest() + '  ' + name + '\n')
        return self.out, summary

    def run_heltec_tx(self):
        """One fixed 915 MHz packet, received by Pluto with TX LO powered down."""
        from pluto_receiver import PlutoReceiver
        started = now_iso()
        info = self.dut.info()
        if not heltec_identity_matches(self.dut.p, info):
            raise RuntimeError('Heltec firmware identity mismatch; no packet armed')
        self.src.disable()
        if not self.sim:
            powerdown = self.src._phy.find_channel('altvoltage1', True).attrs['powerdown'].value
            if powerdown != '1':
                raise RuntimeError('Pluto TX LO shutdown could not be confirmed')
            self.log('Pluto TX LO powerdown=1 verified; receiving on RX1')
        receiver = None
        rx_config = {'frequency_hz': 915000000, 'port': self.cfg['pluto'].get('rx_port', 'A_BALANCED')}

        def transmit():
            arm = self.dut.run('armtx')
            if not arm.get('_done') or str(arm.get('packets')) != '1':
                raise RuntimeError('Heltec did not confirm one-packet arm')
            result = self.dut.run('tx', freq_hz=915000000)
            if not result.get('_done') or not result.get('ok') or not result.get('irq', 0) & 1:
                raise RuntimeError('Heltec TX completion failed: %s' % result)
            return result

        try:
            stopped = self.dut.run('stop')
            if not stopped.get('_done') or str(stopped.get('ok')) != '1':
                raise RuntimeError('Heltec standby not confirmed before test')
            if self.sim:
                tx = transmit()
                blocks = [{'elapsed_s': t, 'rms_dbfs': power, 'clipped_fraction': 0.0,
                           'samples': 8192, 'phase': phase} for t, power, phase in
                          [(0.1, -70, 'baseline'), (0.2, -71, 'baseline'),
                           (0.4, -40, 'trigger'), (0.5, -42, 'trigger'),
                           (0.8, -70, 'post'), (0.9, -71, 'post')]]
            else:
                receiver = PlutoReceiver(self.src, port=rx_config['port'])
                rx_config = receiver.config
                self.log('Pluto RX settings: ' + json.dumps(rx_config))
                blocks, tx = receiver.capture(transmit)
        finally:
            try:
                stopped = self.dut.run('stop')
                if not stopped.get('_done') or str(stopped.get('ok')) != '1':
                    raise RuntimeError('Heltec stop unconfirmed; independently check RF OFF')
            finally:
                try:
                    if receiver is not None:
                        receiver.close()
                finally:
                    self.src.disable()
        with open(os.path.join(self.out, 'pluto_rx_blocks.csv'), 'w', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=list(blocks[0]))
            writer.writeheader()
            writer.writerows(blocks)
        baseline = [r['rms_dbfs'] for r in blocks if r['phase'] == 'baseline']
        during = [r['rms_dbfs'] for r in blocks if r['phase'] == 'trigger']
        post = [r['rms_dbfs'] for r in blocks if r['phase'] == 'post']
        if not baseline or not during or not post:
            raise RuntimeError('Incomplete before/during/after Pluto RX capture')
        floor, level, after = statistics.median(baseline), max(during), statistics.median(post)
        clipped = max(r['clipped_fraction'] for r in blocks)
        delta = level - floor
        reasons = []
        if delta < 10: reasons.append('no_10db_energy_increase')
        if abs(after - floor) > 3: reasons.append('post_capture_not_quiet')
        if clipped > 0: reasons.append('adc_clipping')
        row = dict.fromkeys(MEAS_FIELDS)
        row.update(run_id=self.run_id, order=1, rep=1, freq_hz=915000000,
                   tune_hz=915000000, source_hz=915000000,
                   status='FAIL' if reasons else 'UNVERIFIED',
                   fail_reasons=';'.join(reasons or ['energy_only_packet_not_decoded']),
                   detected=delta >= 10, level_db=level, noise_db=floor,
                   units='dBFS per-component RMS (uncalibrated)', capture_ok=True,
                   source_off_ok=abs(after - floor) <= 3, tx_gain_db=-9,
                   rx_note='One-shot TX; no packet decoding or calibrated power; chip TX setting only',
                   timestamp=now_iso())
        with open(os.path.join(self.out, 'measurements.csv'), 'w', newline='') as fh:
            writer = csv.DictWriter(fh, fieldnames=MEAS_FIELDS)
            writer.writeheader()
            writer.writerow(row)
        summary = self.summarise([915000000], [row])
        meta = {'run_id': self.run_id, 'simulated': self.sim, 'started': started, 'finished': now_iso(),
                'direction': 'heltec-tx-pluto-rx', 'harness_commit': git_commit(),
                'meta': self.cfg['meta'], 'path': self.cfg['path'], 'config': self.cfg,
                'dut': {'profile': self.dut.name, 'info': info, 'tx': tx},
                'pluto': self.src.describe(), 'pluto_rx': rx_config,
                'rx_energy': {'baseline_dbfs': floor, 'trigger_max_dbfs': level, 'post_dbfs': after,
                              'increase_db': delta, 'clipped_fraction': clipped},
                'evidence': 'SIMULATED' if self.sim else 'COMMAND_ACCEPTED',
                'limitations': 'Relative IQ energy only; no LoRa decode, frequency tracking, or calibrated power'}
        with open(os.path.join(self.out, 'meta.json'), 'w') as fh:
            json.dump(meta, fh, indent=2, default=str)
        self.log('RX baseline %.2f dBFS, packet-window max %.2f dBFS, post %.2f dBFS; increase %.2f dB'
                 % (floor, level, after, delta))
        self.print_summary(summary)
        with open(os.path.join(self.out, 'sha256.txt'), 'w') as fh:
            for name in ('meta.json', 'measurements.csv', 'summary.csv', 'pluto_rx_blocks.csv', 'run.log'):
                with open(os.path.join(self.out, name), 'rb') as evidence:
                    fh.write(hashlib.sha256(evidence.read()).hexdigest() + '  ' + name + '\n')
        return self.out, summary

    def run(self):
        t0 = now_iso()
        cfg = self.cfg
        dut_info = self.dut.info()
        if not self.sim and self.dut.p.get("required_firmware_identity") and not heltec_identity_matches(self.dut.p, dut_info):
            raise RuntimeError("DUT firmware identity mismatch; refusing to start RF phases: %s" % dut_info)
        if not self.sim:
            self.ask("board_id", "Board ID / serial")
            self.ask("firmware_commit", "DUT firmware commit")
            self.ask("temperature_c_start", "Room / board temperature now (deg C)")
        if dut_info.get("ok") and dut_info.get("rom") and not cfg["meta"].get("chip_rom_version"):
            cfg["meta"]["chip_rom_version"] = dut_info["rom"]
        if self.sim:
            for k, v in {"board_id": "SIM-BOARD-1", "chip": self.dut.chip, "firmware_commit": "sim",
                         "temperature_c_start": 22.0, "temperature_c_end": 22.5}.items():
                if cfg["meta"].get(k) is None:
                    cfg["meta"][k] = v
        freqs, skipped = self.phase0()
        rtl_res = self.phase1(freqs)
        spurs = self.phase2(freqs)
        self.prompt("Verify the reported conducted path Pluto -> 30 dB fixed attenuator -> 1 ft SMA cable -> Heltec V4.3, with the attenuator on the Pluto output.")
        items = [(rep, f) for rep in range(1, cfg["sweep"]["reps"] + 1) for f in freqs]
        random.Random(self.seed).shuffle(items)
        rows = []
        mpath = os.path.join(self.out, "measurements.csv")
        with open(mpath, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=MEAS_FIELDS)
            w.writeheader()
            try:
                for i, (rep, f) in enumerate(items, 1):
                    row = self.item(i, rep, f, rtl_res, spurs)
                    rows.append(row)
                    w.writerow(row)
                    fh.flush()
            finally:
                self.src.disable()
        if not self.sim:
            self.ask("temperature_c_end", "Temperature at the end (deg C)")
        summary = self.summarise(freqs, rows)
        meta = {"run_id": self.run_id, "simulated": self.sim, "started": t0, "finished": now_iso(),
                "seed": self.seed, "order": [[rep, f] for rep, f in items], "skipped": skipped,
                "meta": cfg["meta"], "path": cfg["path"], "total_loss_db": self.total_loss_db(),
                "pluto": self.src.describe(), "rtl": {"backend": self.rtl.backend if self.rtl else None,
                                                      "note": self.rtl.note if self.rtl else "disabled"},
                "dut": {"profile": self.dut.name, "chip": self.dut.chip, "kind": self.dut.kind, "port": self.dut.t.port,
                        "params": self.dut.params, "info": {k: v for k, v in dut_info.items() if not k.startswith("_")},
                        "profile_sources": self.dut.p.get("source")},
                "derived": {"offset_tol_hz": self.tol, "rbw_hz": self.rbw},
                "harness_commit": git_commit(), "python": sys.version.split()[0], "host": platform.node(),
                "platform": platform.platform(), "warnings": self.warnings, "config": cfg,
                "verdicts": {"%.3f" % (s["freq_hz"] / 1e6): s["verdict"] for s in summary}}
        with open(os.path.join(self.out, "meta.json"), "w") as fh:
            json.dump(meta, fh, indent=2, default=str)
        self.print_summary(summary)
        return self.out, summary

    def summarise(self, freqs, rows):
        p = self.cfg["pass"]
        out = []
        for f in freqs:
            rs = [r for r in rows if r["freq_hz"] == f]
            n = len(rs)
            npass = sum(r["status"] == "PASS" for r in rs)
            nunv = sum(r["status"] == "UNVERIFIED" for r in rs)
            snr = [r["snr_db"] for r in rs if r["snr_db"] is not None]
            evidence_fraction = (npass + nunv) / n if n else 0
            pass_fraction = npass / n if n else 0
            if evidence_fraction >= p["freq_pass_fraction"]:
                verdict = "PASS" if nunv == 0 else "UNVERIFIED"
            else:
                verdict = "FAIL"
            reasons = {}
            for r in rs:
                for x in filter(None, r["fail_reasons"].split(";")):
                    reasons[x] = reasons.get(x, 0) + 1
            med = lambda k: _r(statistics.median([r[k] for r in rs if r[k] is not None])) if any(r[k] is not None for r in rs) else None  # noqa: E731
            out.append({"freq_hz": f, "freq_mhz": f / 1e6, "n": n, "n_pass": npass, "n_unverified": nunv,
                        "pass_fraction": round(pass_fraction, 3), "verdict": verdict,
                        "snr_mean_db": _r(statistics.mean(snr)) if snr else None,
                        "snr_std_db": _r(statistics.stdev(snr)) if len(snr) > 1 else None,
                        "snr_min_db": _r(min(snr)) if snr else None, "noise_median": med("noise_db"),
                        "image_rejection_median_db": med("image_rejection_db"), "ppm_median": med("ppm_dut_vs_pluto"),
                        "mds_tx_gain_median_db": med("mds_tx_gain_db"), "mds_input_median_dbm": med("mds_input_dbm"),
                        "imd_median_dbc": med("imd_dbc"), "rtl_clean": rs[0]["rtl_clean"] if rs else None,
                        "reasons": ";".join("%s x%d" % kv for kv in sorted(reasons.items(), key=lambda kv: -kv[1]))})
        with open(os.path.join(self.out, "summary.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys()) if out else ["freq_hz"])
            w.writeheader()
            w.writerows(out)
        return out

    def print_summary(self, summary):
        self.log("=" * 100)
        self.log("%-10s %-10s %5s %7s %7s %8s %8s %8s  %s" % ("MHz", "verdict", "pass", "SNRavg", "SNRsd", "IRR", "ppm",
                                                             "MDSgain", "reasons"))
        for s in summary:
            self.log("%-10.3f %-10s %2d/%-2d %7s %7s %8s %8s %8s  %s" % (
                s["freq_mhz"], s["verdict"], s["n_pass"], s["n"], s["snr_mean_db"], s["snr_std_db"],
                s["image_rejection_median_db"], s["ppm_median"], s["mds_tx_gain_median_db"], s["reasons"]))
        self.log("results: %s" % self.out)


def _r(v, nd=2):
    return None if v is None else round(float(v), nd)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="JSON file merged over config/default.json")
    ap.add_argument("--sim", action="store_true", help="run against the simulator (no hardware)")
    ap.add_argument("--sim-pluto-range", help="sim only: TX range in Hz, e.g. 70e6:6e9 (default 325e6:3.8e9)")
    ap.add_argument("--profile", help="DUT profile from config/dut_profiles.json")
    ap.add_argument("--port", help="DUT serial port, e.g. COM39")
    ap.add_argument("--serial-number", help="DUT USB serial number instead of --port")
    ap.add_argument("--uri", help="Pluto URI, e.g. ip:192.168.2.1 or usb:")
    ap.add_argument("--fixed-atten-db", type=float, help="fixed attenuator at the Pluto output (required for TX)")
    ap.add_argument("--freqs", help="comma-separated MHz list overriding the config")
    ap.add_argument("--reps", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--label")
    ap.add_argument("--imd", action="store_true", help="also run two-tone IMD (I/Q profiles only)")
    ap.add_argument("--no-rtl", action="store_true")
    ap.add_argument("--out", help="results root (default ./results)")
    ap.add_argument("--yes", action="store_true", help="skip prompts in simulation only")
    ap.add_argument("--arm-rf", action="store_true", help="hardware only: explicitly acknowledge low-power conducted RF work")
    modes = ap.add_mutually_exclusive_group()
    modes.add_argument("--heltec-tx", action="store_true", help="one 915 MHz Heltec packet into Pluto RX1; Pluto TX stays off")
    modes.add_argument("--nominal-check", action="store_true", help="authorized unfiltered 915 MHz baseline only; not a full sweep")
    modes.add_argument("--pll-only", action="store_true", help="RX tuning/error survey; Pluto TX stays off; no RF arming needed")
    modes.add_argument("--receive-check", action="store_true", help="bounded operator-authorized unfiltered RSSI checks, max 20 frequencies, <=3 GHz")
    modes.add_argument('--pluto-relay', action='store_true', help='bounded RX1 99.1 MHz -> conducted TX1 250 MHz relay, max 10 seconds; no Heltec audio claim')
    modes.add_argument("--heltec-audio", action="store_true", help="receive-only one-second RSSI bursts at 99.1 MHz; Pluto TX stays off")
    modes.add_argument("--heltec-modulation", action="store_true", help="bounded conducted 250.001 MHz AM response test; requires RF arming")
    ap.add_argument("--offair-fm", action="store_true", help="with --heltec-audio: receive-only bounded FM-band captures")
    ap.add_argument("--fm-slope", action="store_true", help="with --heltec-modulation: 5kHz-deviation FM filter-slope test")
    ap.add_argument("--arm-heltec-tx", action="store_true", help="arm the bounded reverse-direction test")
    ap.add_argument("--gfsk-probe", action="store_true", help="Heltec fw 1.2: GFSK 4.8 kHz / XOSC / eight RSSI reads")
    ap.add_argument('--rx-offsets-khz', help='receive-check/GFSK only: <=19 signed RX offsets within +/-400 kHz, sources <=340 MHz; fixed -60 dB drive')
    ap.add_argument('--fixed-rx-mhz', type=float, help='receive-check/GFSK only: hold RX fixed while sweeping <=20 nearby sources, <=340 MHz; fixed -60 dB drive')
    ap.add_argument('--gfsk-bandwidth-hz', type=int, choices=(4800,58600,467000), help='Heltec fw1.3: bounded GFSK filter choice, requires --gfsk-probe')
    ap.add_argument("--no-plot", action="store_true")
    a = ap.parse_args(argv)
    if a.offair_fm and not a.heltec_audio:
        print('REFUSED: --offair-fm requires --heltec-audio.'); return 2
    if a.fm_slope and not a.heltec_modulation:
        print('REFUSED: --fm-slope requires --heltec-modulation.'); return 2
    extra = {"dut": {}, "pluto": {}, "path": {}, "sweep": {}, "rtl": {}}
    if a.profile: extra["dut"]["profile"] = a.profile
    if a.port: extra["dut"]["port"] = a.port
    if a.serial_number: extra["dut"]["serial_number"] = a.serial_number
    if a.uri: extra["pluto"]["uri"] = a.uri
    if a.fixed_atten_db is not None: extra["path"]["fixed_atten_db"] = a.fixed_atten_db
    if a.freqs: extra["sweep"]["frequencies_mhz"] = [float(x) for x in a.freqs.split(",")]
    if a.reps: extra["sweep"]["reps"] = a.reps
    if a.imd: extra["sweep"]["imd"] = {"enabled": True}
    if a.no_rtl: extra["rtl"]["enabled"] = False
    if a.heltec_tx or a.nominal_check or a.pll_only or a.receive_check or a.pluto_relay or a.heltec_audio or a.heltec_modulation: extra["rtl"]["enabled"] = False
    if a.label: extra["label"] = a.label
    if a.gfsk_bandwidth_hz is not None and not a.gfsk_probe:
        print('REFUSED: --gfsk-bandwidth-hz requires --gfsk-probe.'); return 2
    if a.gfsk_probe: extra['dut']['overrides'] = {'probe_mode': {4800:'gfsk',58600:'gfsk58',467000:'gfsk467'}[a.gfsk_bandwidth_hz or 4800]}
    if a.rx_offsets_khz:
        if not a.receive_check or not a.gfsk_probe:
            print('REFUSED: --rx-offsets-khz requires --receive-check --gfsk-probe.')
            return 2
        extra['sweep']['rx_offsets_hz'] = [int(round(float(v) * 1000)) for v in a.rx_offsets_khz.split(',')]
    if a.fixed_rx_mhz is not None:
        if not a.receive_check or not a.gfsk_probe or a.rx_offsets_khz:
            print('REFUSED: --fixed-rx-mhz requires --receive-check --gfsk-probe and no RX offsets.')
            return 2
        extra['sweep']['fixed_rx_hz'] = int(round(a.fixed_rx_mhz * 1000000))
    cfg = load_config(a.config, extra)
    if a.gfsk_probe and cfg['dut']['profile'] != 'heltec_v4_3_sx1262':
        print('REFUSED: --gfsk-probe requires the Heltec V4.3 firmware profile.')
        return 2
    if cfg["sweep"]["reps"] < 5:
        print("note: fewer than 5 reps; results will not meet the test plan's repeatability rule")
    rng = None
    if a.sim_pluto_range:
        lo, hi = a.sim_pluto_range.split(":")
        rng = (float(lo), float(hi))
    if not a.sim:
        if a.yes:
            print("REFUSED: --yes is simulation-only; cabling confirmation cannot be bypassed.")
            return 2
    if not a.sim and not (a.pll_only or a.heltec_audio):
        if a.heltec_tx and not a.arm_heltec_tx:
            print('REFUSED: Heltec TX requires --arm-heltec-tx and RX1 conducted-path confirmation.')
            return 2
        if not a.heltec_tx and not a.arm_rf:
            print("REFUSED: real Pluto TX requires --arm-rf, a verified conducted RF path, and an operator confirmation.")
            return 2
        path = cfg["path"]
        if (path.get("fixed_atten_db") is None or path["fixed_atten_db"] < 30 or
                (not a.heltec_tx and not a.nominal_check and not a.receive_check and not a.pluto_relay and not a.heltec_modulation and (not path.get("lowpass_or_bandpass") or
                "TODO" in str(path["lowpass_or_bandpass"]).upper()))):
            print("REFUSED: specify fitted >=30 dB fixed attenuation and an actual source output filter.")
            return 2
        if not cfg["meta"].get("board_revision") or not cfg["meta"].get("fem_part"):
            print("REFUSED: first identify your actual Heltec board revision and RF front-end in config.")
            return 2
        try:
            phrase = ('ARM MODULATION CHECK' if a.heltec_modulation else 'ARM FM RELAY' if a.pluto_relay else 'ARM HELTEC TX' if a.heltec_tx else
                      'ARM UNFILTERED RECEIVE CHECK' if a.receive_check else 'ARM CONDUCTED RF')
            prompt = ('Confirm TX1 -> 30 dB pad -> Heltec, no antennas, authorized unfiltered modulation near250.001MHz at -60dB. Type '
                      if a.heltec_modulation else 'Confirm RX1 monopole and TX1 -> 30 dB pad -> Heltec; authorized bounded unfiltered relay. Type '
                      if a.pluto_relay else
                      'Confirm Heltec -> cable -> 30 dB pad -> Pluto RX1, TX1 disconnected. Type '
                      if a.heltec_tx else
                      'Confirm TX1 -> 30 dB pad -> Heltec and explicit unfiltered range-check authorization. Type '
                      if a.receive_check else
                      'Confirm TX1 -> 30 dB pad -> cable -> Heltec, authorized unfiltered 915 MHz check. Type '
                      if a.nominal_check else 'With TX OFF, verify coax, filter, attenuators and terminations. Type ')
            answer = input(prompt + phrase + ': ')
        except (KeyboardInterrupt, EOFError):
            return 130
        if answer != phrase:
            print("Not armed; no hardware opened.")
            return 2
    runner = None
    try:
        runner = Runner(cfg, a.sim, a.out, a.yes, rng, a.seed)
        if a.pluto_relay:
            from pluto_relay import run_relay
        if a.heltec_audio:
            from heltec_audio import run_capture, run_offair
        if a.heltec_modulation:
            from heltec_audio import run_modulation, run_fm_slope
        out, summary = (run_fm_slope(runner) if a.heltec_modulation and a.fm_slope else run_modulation(runner) if a.heltec_modulation else run_offair(runner) if a.heltec_audio and a.offair_fm else run_capture(runner) if a.heltec_audio else run_relay(runner) if a.pluto_relay else runner.run_pll_only() if a.pll_only else
                        runner.run_heltec_tx() if a.heltec_tx else
                        runner.run_nominal(a.receive_check) if a.nominal_check or a.receive_check else runner.run())
    except KeyboardInterrupt:
        print("aborted; Pluto TX shutdown requested")
        return 130
    except Exception as exc:
        print("harness failure (not a measurement): %s" % exc, file=sys.stderr)
        return 1
    finally:
        if runner is not None:
            runner.close()
    if not a.no_plot and not (a.heltec_tx or a.nominal_check or a.pll_only or a.receive_check or a.pluto_relay or a.heltec_audio or a.heltec_modulation):
        try:
            import plot_results
            plot_results.plot(out)
        except Exception as e:  # noqa: BLE001
            print("plot skipped: %s" % e)
    # FAIL verdicts are results, not errors: exit 0 so scripts can collect them
    return 0


if __name__ == "__main__":
    sys.exit(main())
