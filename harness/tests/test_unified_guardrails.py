# SPDX-License-Identifier: GPL-3.0-only
"""Regressions from the independent unified-harness audit, all offline."""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import dut_serial
import run_sweep
from sim import SimBench


def _m(off, level=-80, snr=30):
    return {"detected": True, "locked": True, "raw_ok": True,
            "offset_hz": off, "level_db": level, "snr_db": snr}


def test_source_off_control_blocks_false_positive():
    p = {"snr_min_db": 10, "require_checks": ["source_shift", "atten_10db", "source_off", "rtl_clean"],
         "atten_tol_db": 2, "level_tol_db": 3, "fail_on_spur_conflict": True}
    a = [_m(20000), _m(25000), None, _m(20000, -90)]
    assert run_sweep.evaluate(*a, True, p, 5000, 4000, 10, 300, False,
                              source_off=_m(20000))[0] == "FAIL"
    quiet = {"detected": False, "locked": True, "raw_ok": True, "offset_hz": None, "snr_db": None}
    assert run_sweep.evaluate(*a, True, p, 5000, 4000, 10, 300, False,
                              source_off=quiet)[0] == "PASS"
    assert run_sweep.evaluate(*a, True, p, 5000, 4000, 10, 300, False,
                              source_off=None)[0] == "UNVERIFIED"


def test_sxprobe_does_not_erase_pll_error_on_unreadable_step():
    d = dut_serial.Dut("lakeshark_sx1262", sim_bench=SimBench())
    good = {"khz": 915020, "err_cal": 0, "err_rx": 0,
            "st_cal": 0, "st_rx": 0, "n": 8, "avg_dbm": -88.0}
    bad = {"khz": 915021, "err_cal": 0, "err_rx": 0x40,
           "st_cal": 0, "st_rx": 0, "n": 0, "avg_dbm": None}
    d.run = lambda *args, **kwargs: {"ok": True, "_done": True,
                                    "restore": "ESP_OK", "rows": [good, bad]}
    m = d._measure_sweep(915000000, 20000, 2000)
    assert m["locked"] is False
    assert m["detected"] is False
    assert m["raw_ok"] is False
    d.close()


def test_incomplete_sxprobe_response_is_not_accepted():
    data = ("sxprobe: start=915000 stop=915001 step=1 points=2\n"
            "sxp,915000,0000,0000,20,50,8,-99,-98,-100,1000\n"
            "sxprobe: end restore=ESP_OK rx=standby\n")
    assert dut_serial.parse_sxprobe(data)["ok"] is False


def test_simulation_never_claims_hardware_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = run_sweep.main(["--sim", "--profile", "sx1262_sdr_tbd",
                         "--freqs", "868", "--reps", "1", "--no-rtl",
                         "--out", str(tmp_path / "runs"), "--no-plot"])
    assert rc == 0
    assert (tmp_path / "SX1262-SDR.log").exists()
    dirs = list((tmp_path / "runs").iterdir())
    assert len(dirs) == 1
    meta = json.loads((dirs[0] / "meta.json").read_text())
    assert meta["simulated"] is True
    assert meta["verdicts"]["868.000"] == "UNVERIFIED"



def test_live_placeholder_fails_before_opening_pluto(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = run_sweep.load_config()
    calls = []
    def no_pluto(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Pluto must never be opened for TODO firmware")
    monkeypatch.setattr(run_sweep, "PlutoSource", no_pluto)
    with __import__("pytest").raises(RuntimeError, match="TODO"):
        run_sweep.Runner(config, sim=False, out_root=str(tmp_path / "runs"))
    assert calls == []


def test_live_requires_explicit_rf_arming(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    called = []
    monkeypatch.setattr(run_sweep, "Runner", lambda *a, **kw: called.append(True))
    assert run_sweep.main(["--no-plot"]) == 2
    assert not called
