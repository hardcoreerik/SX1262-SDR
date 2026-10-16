# SPDX-License-Identifier: GPL-3.0-only
# Part of the SX1262-SDR bench harness. Credits: see harness/README.md.
"""Offline tests: parsers against the firmware's printf formats, pass/fail logic,
TX safety interlock, and full sweeps against the simulator for every profile."""
import csv
import json
import os
import sys
import zlib

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import dut_serial as ds  # noqa: E402
import run_sweep  # noqa: E402
from pluto_source import PlutoSource, SafetyError, parse_available  # noqa: E402

# Lines in the exact shape of the printf calls cited in config/dut_profiles.json
LRPROBE = (
    "lrprobe: f=868000 kHz path=LF bw=31250 rate=125000 gain=9 boost=0 tune=ESP_OK errors=0x0000 bytes=20000 "
    "buf=int max_level=812 polls=400 elapsed_us=40000 flags=0x00 result=ESP_OK recovery=ESP_OK\n"
    "lrprobe-spec: rate=125000 segs=4 dc=0.4,-0.7 rms=110.0 (-49.5 dBFS) floor=20.1 dB "
    "pk1=+19897Hz:+45.3 pk2=-19897Hz:+5.1 pk3=+3052Hz:+4.0\n")
SXPROBE = (
    "sxprobe: start=867990 stop=867992 step=1 kHz bw=4800 code=0x0A gain=0x96 readback=0x96/0x96 reads=8 "
    "settle_us=2000 cal=once modst=0x22 setup=ESP_OK points=3 elapsed_ms=9\n"
    "sxp,khz,err_cal,err_rx,st_cal,st_rx,n,avg_dbm,max_dbm,min_dbm,us\n"
    "sxp,867990,0000,0000,22,2A,8,-118.0,-117.5,-118.5,2900\n"
    "sxp,867991,0000,0040,22,2A,8,-95.5,-95.0,-96.0,2900\n"
    "sxp,867992,0000,0000,22,2A,0,,,,2900\n"
    "sxprobe: end restore=ESP_OK rx=standby\n")


def test_parse_lrprobe():
    r = ds.parse_lrprobe(LRPROBE)
    assert r["ok"] and r["rate"] == 125000 and r["tune"] == "ESP_OK"
    assert r["floor_db"] == pytest.approx(20.1) and r["rms_dbfs"] == pytest.approx(-49.5)
    assert r["peaks"][0] == (19897, 45.3)


def test_parse_sxprobe():
    r = ds.parse_sxprobe(SXPROBE)
    assert r["ok"] and len(r["rows"]) == 3
    assert r["rows"][1]["err_rx"] == 0x40 and r["rows"][1]["avg_dbm"] == -95.5
    assert r["rows"][2]["avg_dbm"] is None and r["restore"] == "ESP_OK"


def test_parse_info():
    r = ds.parse_info("LR2021 ROM 1.24 frequency=868000000 bandwidth=31250 configured=1 errors=0000\n")
    assert r["ok"] and r["rom"] == "1.24"


def test_dump_crc_and_analysis():
    import numpy as np
    n, rate = 8192, 125000
    t = np.arange(n) / rate
    x = 3000 * np.exp(2j * np.pi * 10000 * t) + np.random.default_rng(1).normal(0, 30, n)
    iq = np.empty(2 * n, "<i2"); iq[0::2] = x.real; iq[1::2] = x.imag
    d = iq.tobytes()
    text = "".join("lrfifo-hex: %d %s\n" % (o, d[o:o + 64].hex().upper()) for o in range(0, len(d), 64))
    text += "lrfifo-crc32: %08X bytes=%d encoding=iq16le\n" % (zlib.crc32(d) & 0xFFFFFFFF, len(d))
    r = ds.parse_lrfifo_dump(text)
    assert r["ok"] and r["n"] == len(d)
    a = ds.analyze_iq16le(r["bytes"], rate)
    assert abs(a["peaks"][0][0] - 10000) <= rate / 1024
    assert not ds.parse_lrfifo_dump(text.replace(text.split("lrfifo-crc32: ")[1][:8], "DEADBEEF"))["ok"]


def test_parse_available():
    assert parse_available("[46875001 1 6000000000]") == (46875001, 1, 6000000000)


def _m(off, lvl, snr=30.0):
    return {"detected": True, "locked": True, "offset_hz": off, "level_db": lvl, "snr_db": snr}


P = {"snr_min_db": 10.0, "require_checks": ["source_shift", "retune", "atten_10db", "rtl_clean"],
     "atten_tol_db": 2.0, "level_tol_db": 3.0, "fail_on_spur_conflict": True}


def test_evaluate_pass_and_each_failure():
    base, sh, rt, at = _m(20000, -80), _m(25000, -80), _m(16000, -80), _m(20000, -90)
    assert run_sweep.evaluate(base, sh, rt, at, True, P, 5000, 4000, 10, 300, False)[0] == "PASS"
    # spur that does not follow the source
    assert "source_shift" in run_sweep.evaluate(base, _m(20000, -80), rt, at, True, P, 5000, 4000, 10, 300, False)[1]
    # response that follows the LO the wrong way (e.g. an image)
    assert "retune" in run_sweep.evaluate(base, sh, _m(24000, -80), at, True, P, 5000, 4000, 10, 300, False)[1]
    # compressed / AGC: 10 dB in, 3 dB out
    assert "atten_10db" in run_sweep.evaluate(base, sh, rt, _m(20000, -83), True, P, 5000, 4000, 10, 300, False)[1]
    assert "rtl_clean" in run_sweep.evaluate(base, sh, rt, at, False, P, 5000, 4000, 10, 300, False)[1]
    assert run_sweep.evaluate(base, sh, rt, at, None, P, 5000, 4000, 10, 300, False)[0] == "UNVERIFIED"
    assert "spur_conflict" in run_sweep.evaluate(base, sh, rt, at, True, P, 5000, 4000, 10, 300, True)[1]
    low = _m(20000, -80, snr=6.0)
    assert run_sweep.evaluate(low, sh, rt, at, True, P, 5000, 4000, 10, 300, False)[0] == "FAIL"


def test_tx_safety_interlock(monkeypatch):
    src = PlutoSource(backend="sim")
    src.backend = "iio"  # pretend hardware: the interlock must refuse
    with pytest.raises(SafetyError):
        src._check_safety(-40)          # no fixed attenuator declared
    src.fixed_atten_db = 20
    with pytest.raises(SafetyError):
        src._check_safety(-40)          # attenuator below 30 dB
    src.fixed_atten_db = 40
    with pytest.raises(SafetyError):
        src._check_safety(-5)           # gain above the -20 dB cap
    src._check_safety(-40)              # ok


@pytest.mark.parametrize("profile,freqs", [("lakeshark_sx1262", "433.92,868,2450"),
                                           ("lakeshark_lr2021", "433.92,868,3500"),
                                           ("lr2021_sdr_standalone", "433.92,868"),
                                           ("sx1262_sdr_tbd", "868")])
def test_sim_sweep_end_to_end(tmp_path, profile, freqs):
    rc = run_sweep.main(["--sim", "--profile", profile, "--freqs", freqs, "--reps", "2", "--seed", "3",
                         "--out", str(tmp_path), "--label", "t", "--no-plot"])
    assert rc == 0
    (run,) = os.listdir(tmp_path)
    d = tmp_path / run
    for f in ("meta.json", "measurements.csv", "summary.csv", "spur_map.csv", "source_check.csv", "run.log"):
        assert (d / f).exists(), f
    rows = list(csv.DictReader(open(d / "measurements.csv")))
    assert len(rows) == 2 * len(freqs.split(","))
    meta = json.load(open(d / "meta.json"))
    assert meta["simulated"] and meta["seed"] == 3
    v = meta["verdicts"]
    assert v["868.000"] == "PASS"


def test_plot(tmp_path):
    run_sweep.main(["--sim", "--freqs", "600,868", "--reps", "2", "--out", str(tmp_path), "--no-plot"])
    import plot_results
    (run,) = os.listdir(tmp_path)
    outs = plot_results.plot(str(tmp_path / run))
    assert all(os.path.getsize(o) > 1000 for o in outs)


def test_todo_profile_refuses_real_hardware():
    with pytest.raises(RuntimeError, match="TODO placeholder"):
        ds.Dut("sx1262_sdr_tbd", port="COM_DOES_NOT_EXIST")
