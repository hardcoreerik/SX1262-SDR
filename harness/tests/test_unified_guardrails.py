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


def test_heltec_v43_serial_rows_and_tx_gate_are_versioned():
    profile = dut_serial.load_profiles()["heltec_v4_3_sx1262"]
    info = dut_serial.parse_heltec_info(
        "SX1262-SDR fw=1.6 board=HTIT-WB32LAF-V4.3 fem=KCT8103L tx=one-shot-armed-test-packet\n")
    assert dut_serial.heltec_identity_matches(profile, info)
    assert not dut_serial.heltec_identity_matches(profile, {"ok": False})
    assert not dut_serial.heltec_identity_matches(profile, {**info, "fem": "unknown"})

    probe = dut_serial.parse_heltec_probe(
        "SXPROBE1 f_hz=915000000 dwell_ms=20 ok=1 rssi_dbm=-96.0 status=0x22 errors=0x0000 code=ESP_OK\n")
    assert probe["ok"] and probe["frequency_hz"] == 915000000
    assert probe["rssi_dbm"] == -96.0 and probe["errors"] == 0
    assert dut_serial.parse_heltec_probe("SXPROBE1 broken\n")["ok"] is False

    tx = dut_serial.parse_heltec_tx(
        "SXTX1 f_hz=915000000 ok=1 power_dbm=-9 packets=1 irq=0x01 code=ESP_OK\n")
    assert tx["ok"] and tx["frequency_hz"] == 915000000 and tx["irq"] == 1


def test_heltec_v43_profile_runs_probe_and_tx_protocol_only_in_sim():
    d = dut_serial.Dut("heltec_v4_3_sx1262", sim_bench=SimBench())
    probe = d.run("probe", freq_hz=915000000, dwell_ms=20)
    assert probe["ok"] and probe["frequency_hz"] == 915000000
    assert probe["_done"]
    arm = d.run("armtx")
    assert arm["_done"]
    tx = d.run("tx", freq_hz=915000000)
    assert tx["ok"] and tx["frequency_hz"] == 915000000
    d.close()


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


def test_unverified_rows_do_not_count_as_passes_in_summary(tmp_path):
    runner = object.__new__(run_sweep.Runner)
    runner.cfg = {"pass": {"freq_pass_fraction": 0.8}}
    runner.out = str(tmp_path)
    logged = []
    runner.log = logged.append
    rows = [{"freq_hz": 2700000000.0, "status": "UNVERIFIED", "snr_db": 20.0,
             "fail_reasons": "rtl_unverified", "noise_db": -118.0, "image_rejection_db": None,
             "ppm_dut_vs_pluto": None, "mds_tx_gain_db": None, "mds_input_dbm": None,
             "imd_dbc": None, "rtl_clean": None} for _ in range(5)]

    (summary,) = runner.summarise([2700000000.0], rows)
    runner.print_summary([summary])

    assert summary["verdict"] == "UNVERIFIED"
    assert summary["n_pass"] == 0 and summary["n_unverified"] == 5
    assert summary["pass_fraction"] == 0.0
    assert any("0/5" in line for line in logged)



def test_live_placeholder_fails_before_opening_pluto(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = run_sweep.load_config()
    config["dut"]["profile"] = "sx1262_sdr_tbd"
    calls = []
    def no_pluto(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Pluto must never be opened for TODO firmware")
    monkeypatch.setattr(run_sweep, "PlutoSource", no_pluto)
    with __import__("pytest").raises(RuntimeError, match="TODO"):
        run_sweep.Runner(config, sim=False, out_root=str(tmp_path / "runs"))
    assert calls == []


def test_heltec_live_profile_requires_exact_firmware_identity():
    profile = dut_serial.load_profiles()["heltec_v4_3_sx1262"]
    assert not profile["todo"]
    assert not dut_serial.heltec_identity_matches(profile, dut_serial.parse_heltec_info("SX1262-SDR fw=1.0 init=FAIL\n"))


def test_live_run_refuses_unknown_heltec_firmware_before_rf_phases():
    runner = object.__new__(run_sweep.Runner)
    runner.sim = False
    runner.cfg = {"meta": {}}
    profile = dut_serial.load_profiles()["heltec_v4_3_sx1262"]
    runner.dut = type("DutStub", (), {"p": profile, "info": lambda self: {"ok": False}})()
    with __import__("pytest").raises(RuntimeError, match="firmware identity mismatch"):
        runner.run()


def test_live_requires_explicit_rf_arming(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    called = []
    monkeypatch.setattr(run_sweep, "Runner", lambda *a, **kw: called.append(True))
    assert run_sweep.main(["--no-plot"]) == 2
    assert not called
