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
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from dut_serial import Dut, load_profiles  # noqa: E402
from pluto_source import PlutoSource  # noqa: E402
from rtl_reference import RtlReference  # noqa: E402

MEAS_FIELDS = ["run_id", "order", "rep", "freq_hz", "tune_hz", "source_hz", "status", "fail_reasons", "locked",
               "detected", "snr_db", "level_db", "noise_db", "units", "rbw_hz", "offset_hz", "expected_offset_hz",
               "ppm_dut_vs_pluto", "image_rejection_db", "image_lower_bound", "shift_moved_hz", "shift_ok",
               "retune_moved_hz", "retune_ok", "atten_drop_db", "atten_expected_db", "atten_ok", "rtl_clean",
               "rtl_worst_dbc", "spur_conflict", "tx_gain_db", "input_dbm", "mds_tx_gain_db", "mds_input_dbm",
               "mds_note", "imd_dbc", "imd_lower_bound", "timestamp"]


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
             spur_conflict, unverified_as="unverified"):
    """Pure pass/fail logic. Returns (status, reasons, checks dict)."""
    reasons, checks = [], {}

    def det(m):
        return bool(m and m.get("detected"))

    if not base.get("locked", True):
        reasons.append("no_lock")
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
    unverified = False
    for name in p["require_checks"]:
        c = checks.get(name)
        if c and not c["pass"]:
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
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_id = "%s_%s%s" % (stamp, cfg["label"], "_SIM" if sim else "")
        self.out = os.path.join(out_root or os.path.join(HERE, "results"), self.run_id)
        os.makedirs(self.out, exist_ok=True)
        self._logf = open(os.path.join(self.out, "run.log"), "w", encoding="utf-8")
        self.warnings = []
        prof = load_profiles()[cfg["dut"]["profile"]]
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
        self.dut = Dut(dc["profile"], dc["port"], dc["serial_number"], self.bench, overrides=dc["overrides"],
                       log=self.log_raw)
        d = self.dut.params
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

    # ------------------------------------------------------------ utils --
    def log(self, msg):
        line = "[%s] %s" % (dt.datetime.now().strftime("%H:%M:%S"), msg)
        print(line, flush=True)
        self._logf.write(line + "\n")
        self._logf.flush()

    def log_raw(self, txt):
        self._logf.write(txt + ("\n" if not txt.endswith("\n") else ""))

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
        parts = [pth["fixed_atten_db"], pth["cable_loss_db"], pth["step_atten_db"]]
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
        expect = [d, d + s, -d]  # spur offsets are stored relative to F for both tunes
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
        retune = self.measure(f + r, src_hz, g0, o0 - r, 3 * self.tol)
        att = self.measure(f, src_hz, g0 - a, o0, 3 * self.tol)
        rr = rtl_res.get(f, {})
        rtl_clean = rr.get("clean") if rr else None
        step = rr.get("source_step_10db_measured") if rr else None
        atten_expected = step if (step is not None and abs(step - a) <= 1.5) else a
        conflict = self.spur_conflict(f, spurs)
        status, reasons, checks = evaluate(base, shift, retune, att, rtl_clean, p, s, r, atten_expected, self.tol,
                                           conflict, p.get("unverified_rtl_counts_as", "unverified"))
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
               "retune_moved_hz": _r(checks["retune"]["moved_hz"]), "retune_ok": checks["retune"]["pass"],
               "atten_drop_db": _r(checks["atten_10db"].get("drop_db")), "atten_expected_db": atten_expected,
               "atten_ok": checks["atten_10db"]["pass"], "rtl_clean": rtl_clean, "rtl_worst_dbc": rr.get("worst_dbc") if rr else None,
               "spur_conflict": conflict, "tx_gain_db": g0, "input_dbm": self.input_dbm(g0),
               "mds_tx_gain_db": mds_g, "mds_input_dbm": self.input_dbm(mds_g) if mds_g is not None else None,
               "mds_note": mds_note, "imd_dbc": imd_v, "imd_lower_bound": imd_lb, "timestamp": now_iso()}
        self.log("#%03d rep%d %9.3f MHz %-10s snr=%s shift=%s retune=%s att=%s rtl=%s mds_gain=%s %s" % (
            order, rep, f / 1e6, status, row["snr_db"], row["shift_ok"], row["retune_ok"], row["atten_drop_db"],
            rtl_clean, mds_g, row["fail_reasons"]))
        return row

    # -------------------------------------------------------------- run --
    def run(self):
        t0 = now_iso()
        cfg = self.cfg
        if not self.sim:
            self.ask("board_id", "Board ID / serial")
            self.ask("firmware_commit", "DUT firmware commit")
            self.ask("temperature_c_start", "Room / board temperature now (deg C)")
        dut_info = self.dut.info()
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
        self.prompt("Connect the source path to the DUT: Pluto -> filter -> fixed attenuator -> step attenuator -> DUT.")
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
        self.dut.close()
        if self.rtl:
            self.rtl.close()
        self._logf.close()
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
            frac = (npass + nunv) / n if n else 0
            if frac >= p["freq_pass_fraction"]:
                verdict = "PASS" if nunv == 0 else "UNVERIFIED"
            else:
                verdict = "FAIL"
            reasons = {}
            for r in rs:
                for x in filter(None, r["fail_reasons"].split(";")):
                    reasons[x] = reasons.get(x, 0) + 1
            med = lambda k: _r(statistics.median([r[k] for r in rs if r[k] is not None])) if any(r[k] is not None for r in rs) else None  # noqa: E731
            out.append({"freq_hz": f, "freq_mhz": f / 1e6, "n": n, "n_pass": npass, "n_unverified": nunv,
                        "pass_fraction": round(frac, 3), "verdict": verdict,
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
                s["freq_mhz"], s["verdict"], s["n_pass"] + s["n_unverified"], s["n"], s["snr_mean_db"], s["snr_std_db"],
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
    ap.add_argument("--yes", action="store_true", help="do not wait at cabling prompts (only for fixed setups)")
    ap.add_argument("--no-plot", action="store_true")
    a = ap.parse_args(argv)
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
    if a.label: extra["label"] = a.label
    cfg = load_config(a.config, extra)
    if cfg["sweep"]["reps"] < 5:
        print("note: fewer than 5 reps; results will not meet the test plan's repeatability rule")
    rng = None
    if a.sim_pluto_range:
        lo, hi = a.sim_pluto_range.split(":")
        rng = (float(lo), float(hi))
    runner = Runner(cfg, a.sim, a.out, a.yes, rng, a.seed)
    try:
        out, summary = runner.run()
    except KeyboardInterrupt:
        runner.src.disable()
        print("aborted; Pluto TX disabled")
        return 130
    if not a.no_plot:
        try:
            import plot_results
            plot_results.plot(out)
        except Exception as e:  # noqa: BLE001
            print("plot skipped: %s" % e)
    # FAIL verdicts are results, not errors: exit 0 so scripts can collect them
    return 0


if __name__ == "__main__":
    sys.exit(main())
