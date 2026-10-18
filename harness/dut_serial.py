# SPDX-License-Identifier: GPL-3.0-only
# Part of the SX1262-SDR bench harness. Credits: see harness/README.md.
"""Serial wrapper for DUT receive probes and bounded Heltec test transmit commands.

The console formats parsed here are those of SAMS0N1TE's GPL-3.0 projects lr2021-sdr and
LakeShark (file:line evidence in config/dut_profiles.json).

All command text, completion patterns and parsers are chosen from the table in
config/dut_profiles.json, so a new firmware (the SX1262-SDR repo) only needs a new profile.

Profiles shipped (see the "source" list in each for file:line evidence):
  lakeshark_sx1262      `lora sxprobe ...`  RSSI sweep, one CSV row per step
  lakeshark_lr2021      `lora lrprobe ...`  I/Q capture + on-board 1024-bin spectrum, top 3 peaks
  lr2021_sdr_standalone `tune` / `capture` / `dump` / `info` of SAMS0N1TE/lr2021-sdr firmware;
                        the hex dump is CRC-checked and analysed on the host
  sx1262_sdr_tbd        placeholder for the new repo

measure() returns one normalised dict for every profile:
  detected, level_db, noise_db, snr_db, offset_hz, image_db, image_lower_bound, rbw_hz,
  units, locked, peaks, raw_ok, note, raw (last console text)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
KV = re.compile(r"(\w+)=(\S+)")
PK = re.compile(r"pk(\d)=([+-]\d+)Hz:([+-]?[\d.]+)")


def load_profiles(path=None):
    with open(path or os.path.join(HERE, "config", "dut_profiles.json")) as fh:
        d = json.load(fh)
    return {k: v for k, v in d.items() if not k.startswith("_")}


# ---------------------------------------------------------------- parsers --
def parse_kv(text):
    out = {}
    for line in text.splitlines():
        for k, v in KV.findall(line):
            out[k] = v
    return out


def parse_info(text):
    m = re.search(r"LR2021 ROM (\d+)\.(\d+) frequency=(\d+) bandwidth=(\d+) configured=(\d+) errors=([0-9A-Fa-f]{4})", text)
    if not m:
        return {"ok": False}
    return {"ok": True, "chip": "LR2021", "rom": "%s.%s" % (m.group(1), m.group(2)), "frequency_hz": int(m.group(3)),
            "bandwidth_hz": int(m.group(4)), "configured": int(m.group(5)), "errors": m.group(6)}


def parse_lrprobe(text):
    """`lrprobe:` + `lrprobe-spec:` lines (ls_lora_lr20xx.c:4238-4244, 4154-4174)."""
    out = {"ok": False, "peaks": []}
    m = re.search(r"^lrprobe: (f=.*)$", text, re.M)
    if m:
        line = m.group(1)
        d = dict(KV.findall(line))
        out.update({k: d[k] for k in d})
        out["f_khz"] = int(d.get("f", "0"))
        out["bytes"] = int(d.get("bytes", "0"))
        out["rate"] = int(d.get("rate", "0"))
        n = re.search(r"errors=0x[0-9A-Fa-f]{4} ([A-Z0-9_| ]+?) bytes=", line)
        out["err_names"] = n.group(1).strip() if n else ""
        out["errors"] = int(d.get("errors", "0x0"), 16)
    s = re.search(r"^lrprobe-spec: (.*)$", text, re.M)
    if s:
        line = s.group(1)
        d = dict(KV.findall(line))
        out["rate"] = int(d.get("rate", out.get("rate", 0)))
        fl = re.search(r"floor=([-\d.]+) dB", line)
        out["floor_db"] = float(fl.group(1)) if fl else None
        r = re.search(r"\(([-\d.]+) dBFS\)", line)
        out["rms_dbfs"] = float(r.group(1)) if r else None
        out["peaks"] = [(int(hz), float(db)) for _, hz, db in sorted(PK.findall(line))]
        out["ok"] = True
    out["usage"] = "usage: lora lrprobe" in text
    return out


def parse_sxprobe(text):
    """`sxprobe:` header, `sxp,...` rows, `sxprobe: end` (ls_lora_sx126x.c:1230-1251)."""
    out = {"ok": False, "rows": []}
    h = re.search(r"^sxprobe: start=.*$", text, re.M)
    if h:
        out["header"] = dict(KV.findall(h.group(0)))
    for line in text.splitlines():
        if not line.startswith("sxp,") or line.startswith("sxp,khz"):
            continue
        p = line.strip().split(",")
        if len(p) != 11:
            continue
        row = {"khz": int(p[1]), "err_cal": int(p[2], 16), "err_rx": int(p[3], 16), "st_cal": int(p[4], 16),
               "st_rx": int(p[5], 16), "n": int(p[6]), "us": int(p[10])}
        for i, k in ((7, "avg_dbm"), (8, "max_dbm"), (9, "min_dbm")):
            row[k] = float(p[i]) if p[i] else None
        out["rows"].append(row)
    e = re.search(r"^sxprobe: end restore=(\S+) rx=(.*)$", text, re.M)
    if e:
        out["restore"], out["rx"] = e.group(1), e.group(2).strip()
        out["ok"] = bool(out["rows"]) and out["restore"] == "ESP_OK" and bool(h) and (not out.get("header", {}).get("points") or len(out["rows"]) == int(out["header"]["points"]))
    out["usage"] = "usage: lora sxprobe" in text
    return out


def parse_heltec_probe(text):
    """Versioned RSSI/status row from the SX1262-SDR Heltec V4.3 firmware."""
    m = re.search(r"^SXPROBE1 (.*)$", text, re.M)
    if not m:
        return {"ok": False}
    fields = dict(KV.findall(m.group(1)))
    try:
        return {"ok": fields.get("ok") == "1", "frequency_hz": int(fields["f_hz"]),
                "dwell_ms": int(fields["dwell_ms"]),
                "rssi_dbm": float(fields["rssi_dbm"]) if fields.get('ok') == '1' else None,
                "status": int(fields["status"], 16), "errors": int(fields["errors"], 16),
                "code": fields.get("code", ""), "mode": fields.get("mode"),
                "bandwidth_hz": int(fields.get("bw_hz", "0")),
                "reads": int(fields.get("reads", "1")),
                "cal_errors": int(fields.get("cal_errors", "0"), 16)}
    except (KeyError, ValueError):
        return {"ok": False}


def parse_heltec_audio(text):
    """Strict ordered capture framing; reject incomplete or corrupted bursts."""
    try:
        lines = text.strip().splitlines()
        headers = [i for i, line in enumerate(lines) if line.startswith('SXCAP1 ')]
        ends = [i for i, line in enumerate(lines) if line.startswith('SXCAPEND1 ')]
        if len(headers) != 1 or len(ends) != 1 or headers[0] >= ends[0]:
            return {'ok': False}
        h = dict(KV.findall(lines[headers[0]]))
        e = dict(KV.findall(lines[ends[0]]))
        data = bytearray()
        for line in lines[headers[0]+1:ends[0]]:
            m = re.fullmatch(r'SXDATA1 offset=(\d+) hex=([0-9A-Fa-f]+)', line)
            if not m or int(m[1]) != len(data): return {'ok': False}
            data.extend(bytes.fromhex(m[2]))
        n, rate = int(h['n']), int(h['rate_hz'])
        status, errors = int(h['status'], 16), int(h['errors'], 16)
        cs = (status >> 1) & 7
        ok = (h['ok'] == '1' and h['code'] == 'ESP_OK' and e['stop'] == '1' and
              errors == 0 and int(h.get('cal_errors', '0'), 16) == 0 and
              (status >> 4) & 7 == 5 and cs not in (3, 4, 5, 7) and
              1 < n <= rate and rate in (1000, 2000, 4000, 8000) and
              (88000000 <= int(h['f_hz']) <= 108000000 or int(h['f_hz']) == 250001000) and int(h['bw_hz']) in (58600, 467000) and
              len(data) == n * 7 == int(e['bytes']) and len(e['crc32']) == 8 and
              zlib.crc32(data) & 0xFFFFFFFF == int(e['crc32'], 16))
        return {'ok': bool(ok), 'data': bytes(data), 'n': n, 'rate_hz': rate,
                'frequency_hz': int(h['f_hz']), 'bandwidth_hz': int(h['bw_hz']), 'status': status, 'errors': errors}
    except (KeyError, ValueError):
        return {'ok': False}


def parse_heltec_tx(text):
    m = re.search(r"^SXTX1 (.*)$", text, re.M)
    if not m:
        return {"ok": False}
    fields = dict(KV.findall(m.group(1)))
    try:
        fields["ok"] = fields.get("ok") == "1"
        if "f_hz" in fields:
            fields["frequency_hz"] = int(fields["f_hz"])
        if "irq" in fields:
            fields["irq"] = int(fields["irq"], 16)
        return fields
    except ValueError:
        return {"ok": False}


def parse_heltec_info(text):
    """Board and firmware identity emitted by the local Heltec V4.3 image."""
    m = re.search(r"^SX1262-SDR fw=(\S+) board=(\S+) fem=(\S+)(?:\s+.*)?$", text, re.M)
    if not m:
        return {"ok": False}
    return {"ok": True, "firmware": m.group(1), "board": m.group(2), "fem": m.group(3)}


def heltec_identity_matches(profile, info):
    required = profile.get("required_firmware_identity", {})
    return bool(info.get("ok") and required and all(info.get(k) == v for k, v in required.items()))


def parse_lrfifo_dump(text):
    """`lrfifo-hex:` lines + `lrfifo-crc32:` (SDR main.c:76-90). Returns bytes and CRC status."""
    chunks = {}
    for m in re.finditer(r"^lrfifo-hex: (\d+) ([0-9A-Fa-f]+)\s*$", text, re.M):
        chunks[int(m.group(1))] = bytes.fromhex(m.group(2))
    data = b"".join(chunks[k] for k in sorted(chunks))
    c = re.search(r"^lrfifo-crc32: ([0-9A-Fa-f]{8}) bytes=(\d+) encoding=(\S+)", text, re.M)
    out = {"bytes": data, "n": len(data), "ok": False}
    if c:
        out["crc_expected"] = c.group(1).upper()
        out["crc_actual"] = "%08X" % (zlib.crc32(data) & 0xFFFFFFFF)
        out["ok"] = out["crc_expected"] == out["crc_actual"] and int(c.group(2)) == len(data)
    return out


def analyze_iq16le(data, rate, n=1024, npeaks=8):
    """Python re-implementation of the algorithm in LakeShark's probe_report() (ls_lora_lr20xx.c:4122-4175): averaged Hann spectrum,
    DC removed, floor = median bin, strongest peaks away from DC (>=4 bins apart)."""
    import numpy as np
    iq = np.frombuffer(data[: len(data) // 4 * 4], dtype="<i2").astype(float)
    x = iq[0::2] + 1j * iq[1::2]
    segs = len(x) // n
    if segs < 1:
        return {"ok": False}
    x = x - x.mean()
    w = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)
    p = np.zeros(n)
    for s in range(segs):
        p += np.abs(np.fft.fft(x[s * n:(s + 1) * n] * w)) ** 2
    floor = max(float(np.median(p)), 1e-9)
    peaks, taken = [], []
    order = np.argsort(p)[::-1]
    for k in order:
        if k < 3 or k > n - 3 or any(abs(int(k) - t) < 4 for t in taken):
            continue
        taken.append(int(k))
        off = (k if k < n // 2 else k - n) * rate / n
        peaks.append((int(off), float(10 * math.log10(p[k] / floor))))
        if len(peaks) >= npeaks:
            break
    rms = float(np.sqrt(np.mean(iq ** 2) * 2))
    return {"ok": True, "rate": rate, "segs": segs, "floor_db": 10 * math.log10(floor), "peaks": peaks,
            "rms_dbfs": 20 * math.log10(rms / 32768 + 1e-12)}


PARSERS = {"kv": parse_kv, "info": parse_info, "lrprobe": parse_lrprobe, "sxprobe": parse_sxprobe,
           "heltec_probe": parse_heltec_probe, "heltec_tx": parse_heltec_tx, "heltec_info": parse_heltec_info,
           "heltec_audio": parse_heltec_audio,
           "lrfifo_dump": parse_lrfifo_dump}


# ------------------------------------------------------------- transports --
class SerialTransport:
    def __init__(self, port=None, serial_number=None, baud=115200):
        import serial
        from serial.tools import list_ports
        if not port and serial_number:
            port = next((p.device for p in list_ports.comports() if p.serial_number == serial_number), None)
        if not port:
            raise RuntimeError("DUT serial port not found (give --port COMx or --serial-number)")
        s = serial.Serial()
        s.port, s.baudrate, s.timeout = port, baud, 0.1
        s.dtr = False  # keep the ESP32 out of reset/bootloader (as lrprobe.py:22 does)
        s.rts = False
        s.open()
        time.sleep(0.3)
        s.read(65536)
        self.s, self.port = s, port

    def exchange(self, line, done_re, timeout_s):
        self.s.read(65536)
        self.s.write(line.encode() + b"\r\n")
        buf, end = "", time.time() + timeout_s
        rx = re.compile(done_re, re.M)
        while time.time() < end:
            buf += self.s.read(8192).decode("utf-8", "replace")
            if rx.search(buf.replace("\r", "")):
                time.sleep(0.05)
                buf += self.s.read(8192).decode("utf-8", "replace")
                return buf.replace("\r", ""), True
        return buf.replace("\r", ""), False

    def close(self):
        self.s.close()


class SimTransport:
    """Answers like the real firmware, from SimBench. Output formats copy the printf calls
    cited in dut_profiles.json so the same parsers are exercised."""

    def __init__(self, bench, profile):
        self.bench, self.profile = bench, profile
        self.port = "SIM"
        self._tuned = None
        self._iq = b""

    def exchange(self, line, done_re, timeout_s):
        a = line.split()
        if a and a[0] == "info" and self.profile.get("board") == "HTIT-WB32LAF-V4.3":
            return "SX1262-SDR fw=1.6 board=HTIT-WB32LAF-V4.3 fem=KCT8103L rx_min_hz=1000000 rx_modes=lora,gfsk tx=one-shot-armed-test-packet\n", True
        if a and a[0] == "probe" and self.profile.get("board") == "HTIT-WB32LAF-V4.3":
            hz, dwell = int(a[1]), int(a[2])
            level = self.bench.sx_rssi(hz / 1000.0, 4800)
            errors = 0 if level is not None else 0x0040
            if level is None:
                level = self.bench.rssi_floor_dbm
            gfsk = len(a) > 3 and a[3] in ('gfsk', 'gfsk58', 'gfsk467')
            bw = {'gfsk':4800,'gfsk58':58600,'gfsk467':467000}.get(a[3] if len(a)>3 else 'lora',125000)
            return ("SXPROBE1 f_hz=%d dwell_ms=%d ok=%d rssi_dbm=%.1f status=0x%02X errors=0x%04X code=ESP_OK mode=%s bw_hz=%d reads=%d cal_errors=0x0000\n"
                    % (hz, dwell, not errors, level, 0x3A if errors else 0x52, errors,
                       'gfsk' if gfsk else 'lora', bw,
                       0 if errors else 8 if gfsk else 1)), True
        if a and a[0] == "armtx" and self.profile.get("board") == "HTIT-WB32LAF-V4.3":
            return "SXTXARM1 packets=1 power_dbm=-9 expires_ms=30000\n", True
        if a and a[0] == "stop" and self.profile.get("board") == "HTIT-WB32LAF-V4.3":
            return "SXSTOP1 ok=1 code=ESP_OK\n", True
        if a and a[0] == "tx" and self.profile.get("board") == "HTIT-WB32LAF-V4.3":
            return "SXTX1 f_hz=%s ok=1 power_dbm=-9 packets=1 irq=0x01 code=ESP_OK\n" % a[1], True
        if a and a[0] == "TODO-sxprobe":  # placeholder profile: simulate it with sxprobe semantics
            a = ["lora", "sxprobe"] + a[1:]
        if a[:2] == ["lora", "sxprobe"]:
            return self._sx(a), True
        if a[:2] == ["lora", "lrprobe"]:
            return self._lr(a), True
        if a[0] == "tune":
            self._tuned = int(a[1])
            return "tune: %d Hz result=%d\n" % (self._tuned, 0 if self.bench.locked(self._tuned) else -1), True
        if a[0] == "info":
            return "LR2021 ROM 1.24 frequency=%d bandwidth=31250 configured=1 errors=0000\n" % (self._tuned or 0), True
        if a[0] == "capture":
            return self._capture(int(a[1])), True
        if a[0] == "dump":
            return self._dump(), True
        return "Unrecognized command\n", False

    def _sx(self, a):
        start, stop, step, bw = int(a[2]), int(a[3]), int(a[4]), int(a[5])
        reads = int(a[7])
        lines = ["sxprobe: start=%d stop=%d step=%d kHz bw=%d code=0x0A gain=0x96 readback=0x96/0x96 reads=%d "
                 "settle_us=%s cal=%s modst=0x22 setup=ESP_OK points=%d elapsed_ms=%d"
                 % (start, stop, step, bw, reads, a[8], a[9], (stop - start) // step + 1, 5),
                 "sxp,khz,err_cal,err_rx,st_cal,st_rx,n,avg_dbm,max_dbm,min_dbm,us"]
        for khz in range(start, stop + 1, step):
            p = self.bench.sx_rssi(khz, bw)
            err = 0 if p is not None else 0x0040
            if p is None:
                p = self.bench.rssi_floor_dbm
            raws = [min(255, max(0, int(round(-2 * (p + self.bench.rng.gauss(0, 0.6)))))) for _ in range(reads)]
            avg = -sum(raws) / (2.0 * reads)
            lines.append("sxp,%d,0000,%04X,22,2A,%d,%.1f,%.1f,%.1f,%d" % (khz, err, reads, avg, -min(raws) / 2.0,
                                                                         -max(raws) / 2.0, 2900))
        lines.append("sxprobe: end restore=ESP_OK rx=standby")
        return "\n".join(lines) + "\n"

    def _lr(self, a):
        khz, bw, gain, ms = int(a[2]), int(a[3]), int(a[4]), int(a[7])
        rate = 4 * bw
        sp = self.bench.lr_spectrum(khz * 1000, rate, gain)
        path = "HF" if khz * 1000 >= 1.5e9 else "LF"
        if sp is None:
            return ("lrprobe: f=%d kHz path=%s bw=%d rate=%d gain=%d boost=0 tune=ESP_FAIL errors=0x0040 PLL_LOCK "
                    "bytes=0 buf=int max_level=0 polls=0 elapsed_us=0 flags=0x00 result=ESP_FAIL recovery=ESP_OK\n"
                    % (khz, path, bw, rate, gain))
        nbytes = ms * rate // 1000 * 4
        head = ("lrprobe: f=%d kHz path=%s bw=%d rate=%d gain=%d boost=0 tune=ESP_OK errors=0x0000 bytes=%d buf=int "
                "max_level=812 polls=400 elapsed_us=%d flags=0x00 result=ESP_OK recovery=ESP_OK\n"
                % (khz, path, bw, rate, gain, nbytes, ms * 1000))
        spec = "lrprobe-spec: rate=%d segs=%d dc=0.4,-0.7 rms=110.0 (-49.5 dBFS) floor=%.1f dB" % (
            rate, nbytes // 4 // 1024, sp["floor_db"])
        for i, (off, db) in enumerate(sp["peaks"]):
            spec += " pk%d=%+dHz:%+.1f" % (i + 1, int(off), db)
        return head + spec + "\n"

    def _capture(self, ms):
        import numpy as np
        rate = 125000
        n = ms * rate // 1000
        sp = self.bench.lr_spectrum(self._tuned or 0, rate) if self._tuned else None
        rng = np.random.default_rng(self.bench.rng.randrange(1 << 30))
        noise_amp = 60.0  # sim: about -58 dBFS noise, as the rx-range README reports
        x = (rng.normal(0, noise_amp / math.sqrt(2), n) + 1j * rng.normal(0, noise_amp / math.sqrt(2), n))
        t = np.arange(n) / rate
        if sp:
            for off, db in sp["peaks"]:
                if db > 9:
                    amp = noise_amp * 10 ** (db / 20) / math.sqrt(1024 * 0.375)
                    x += amp * np.exp(2j * np.pi * off * t)
        iq = np.empty(2 * n, dtype="<i2")
        iq[0::2] = np.clip(x.real, -32768, 32767)
        iq[1::2] = np.clip(x.imag, -32768, 32767)
        self._iq = iq.tobytes()
        return ("check: accepted=%d elapsed_us=%d peak=820 service_gap_us=1600 flags=00 capture=0 recovery=0 "
                "rejected=0 result=PASS\n" % (len(self._iq), ms * 1000))

    def _dump(self):
        d = self._iq
        if not d:
            return "run a successful capture first\n"
        lines = ["lrfifo-hex: %d %s" % (o, d[o:o + 64].hex().upper()) for o in range(0, len(d), 64)]
        lines.append("lrfifo-crc32: %08X bytes=%d encoding=iq16le" % (zlib.crc32(d) & 0xFFFFFFFF, len(d)))
        lines.append("lrfifo: bytes=%d max_level=820 polls=1 elapsed_us=0 flags=0x00 result=ESP_OK recovery=ESP_OK"
                     % len(d))
        return "\n".join(lines) + "\n"

    def close(self):
        pass


# ------------------------------------------------------------------- DUT --
class Dut:
    def __init__(self, profile_name, port=None, serial_number=None, sim_bench=None, profiles_path=None,
                 overrides=None, log=None):
        profiles = load_profiles(profiles_path)
        if profile_name not in profiles:
            raise KeyError("unknown DUT profile %r (have: %s)" % (profile_name, ", ".join(profiles)))
        self.name = profile_name
        self.p = profiles[profile_name]
        if self.p.get("todo") and sim_bench is None:
            raise RuntimeError("DUT profile %r is a TODO placeholder (%s). Use --sim, or fill it in in "
                               "config/dut_profiles.json first." % (profile_name, self.p.get("status", "")))
        self.params = dict(self.p.get("defaults", {}))
        self.params.update(overrides or {})
        self.log = log
        if sim_bench is not None:
            self.t = SimTransport(sim_bench, self.p)
        else:
            self.t = SerialTransport(port, serial_number, self.p.get("baud", 115200))
        self.last_raw = ""

    @property
    def chip(self):
        return self.p["chip"]

    @property
    def kind(self):
        return self.p["kind"]

    def covers(self, hz):
        return self.p["freq_min_hz"] <= hz <= self.p["freq_max_hz"]

    def run(self, cmd, timeout_s=None, **fmt):
        spec = self.p["commands"].get(cmd)
        if not spec:
            raise KeyError("profile %s has no command %r" % (self.name, cmd))
        line = spec["template"].format(**{**self.params, **fmt})
        raw, done = self.t.exchange(line, spec["done_regex"], timeout_s or spec["timeout_s"])
        self.last_raw = raw
        if self.log:
            self.log("> %s\n%s" % (line, raw if len(raw) < 4000 else raw[:4000] + "...[truncated]\n"))
        parsed = PARSERS[spec["parser"]](raw)
        if isinstance(parsed, dict):
            parsed["_done"] = done
            parsed["_cmd"] = line
        return parsed

    def info(self):
        if self.p["commands"].get("info"):
            try:
                return self.run("info")
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "error": str(e)}
        return {"ok": False, "note": "profile has no info command; enter chip/ROM/firmware by hand"}

    # ----------------------------------------------------------- measure --
    def measure(self, tune_hz, expect_offset_hz, window_hz, image=True):
        """Tune to tune_hz, look for a tone near expect_offset_hz (+-window_hz)."""
        if self.kind == "iq_peaks":
            return self._measure_lrprobe(tune_hz, expect_offset_hz, window_hz, image)
        if self.kind == "iq_dump":
            return self._measure_dump(tune_hz, expect_offset_hz, window_hz, image)
        return self._measure_sweep(tune_hz, expect_offset_hz, window_hz)

    def spur_scan(self, tune_hz, threshold_db):
        """Terminated input: peaks (offset_hz, dB over floor) above threshold."""
        m = self.measure(tune_hz, 0.0, 0.0, image=False)
        return m, [(o, d) for o, d in m.get("peaks", []) if d >= threshold_db]

    @staticmethod
    def _pick(peaks, expect, window):
        cands = [(o, d) for o, d in peaks if abs(o - expect) <= window]
        return max(cands, key=lambda x: x[1]) if cands else None

    def _result_from_peaks(self, peaks, floor_db, rbw, expect, window, image, units, locked, note=""):
        hit = self._pick(peaks, expect, window) if window > 0 else None
        res = {"detected": hit is not None, "locked": locked, "noise_db": floor_db, "rbw_hz": rbw, "units": units,
               "peaks": peaks, "raw_ok": True, "note": note, "image_db": None, "image_lower_bound": False}
        if hit:
            res.update(offset_hz=float(hit[0]), snr_db=float(hit[1]), level_db=floor_db + hit[1])
            if image:
                img = self._pick([p for p in peaks if p != hit], -hit[0], max(3 * rbw, 300.0))
                if img:
                    res["image_db"] = round(hit[1] - img[1], 2)
                else:
                    others = [p[1] for p in peaks if p != hit]
                    weakest = min(others) if others else 0.0
                    res["image_db"] = round(hit[1] - weakest, 2)
                    res["image_lower_bound"] = True
        else:
            res.update(offset_hz=None, snr_db=None, level_db=None)
        return res

    def _measure_lrprobe(self, tune_hz, expect, window, image):
        q = dict(self.params)
        r = self.run("probe", khz=int(round(tune_hz / 1000)), **q)
        locked = r.get("tune") == "ESP_OK" and r.get("bytes", 0) > 0
        if not r.get("ok"):
            return {"detected": False, "locked": locked, "raw_ok": False, "snr_db": None, "level_db": None,
                    "offset_hz": None, "noise_db": None, "peaks": [], "image_db": None, "image_lower_bound": False,
                    "rbw_hz": None, "units": "dB digital",
                    "note": "no spectrum: tune=%s errors=%s %s" % (r.get("tune"), r.get("errors"), r.get("err_names", ""))}
        rate = r["rate"]
        # lrprobe tunes in whole kHz: correct the expected offset for the rounding
        expect_adj = expect + (tune_hz - int(round(tune_hz / 1000)) * 1000)
        return self._result_from_peaks(r["peaks"], r["floor_db"], rate / 1024.0, expect_adj, window, image,
                                       "dB digital (uncalibrated)", locked,
                                       "only the 3 strongest peaks are reported by lrprobe")

    def _measure_dump(self, tune_hz, expect, window, image):
        t = self.run("tune", hz=int(round(tune_hz)))
        if t.get("result", "-1") != "0":
            return {"detected": False, "locked": False, "raw_ok": False, "snr_db": None, "level_db": None,
                    "offset_hz": None, "noise_db": None, "peaks": [], "image_db": None, "image_lower_bound": False,
                    "rbw_hz": None, "units": "dB digital", "note": "tune failed"}
        c = self.run("capture", ms=self.params.get("ms", 100))
        d = self.run("dump")
        if c.get("result") != "PASS" or not d.get("ok"):
            return {"detected": False, "locked": True, "raw_ok": False, "snr_db": None, "level_db": None,
                    "offset_hz": None, "noise_db": None, "peaks": [], "image_db": None, "image_lower_bound": False,
                    "rbw_hz": None, "units": "dB digital", "note": "capture %s / dump crc ok=%s" % (c.get("result"), d.get("ok"))}
        rate = self.params.get("rate", 125000)
        a = analyze_iq16le(d["bytes"], rate)
        return self._result_from_peaks(a["peaks"], a["floor_db"], rate / 1024.0, expect, window, image,
                                       "dB digital (uncalibrated)", True, "host FFT of CRC-checked dump")

    def _measure_sweep(self, tune_hz, expect, window):
        q = dict(self.params)
        span, step = q.pop("span_hz", 50000), q.pop("step_hz", 1000)
        centre = tune_hz + expect
        half = max(span / 2, window + 3 * q.get("bw", 4800))
        start = int((centre - half) // 1000)
        stop = int((centre + half) // 1000)
        step_khz = max(1, int(step // 1000))
        pts = (stop - start) // step_khz + 1
        if self.p.get("instant_probe"):
            return self._measure_heltec_sweep(tune_hz, expect, window, start * 1000,
                                              stop * 1000, step_khz * 1000, pts)
        spec = self.p["commands"]["probe"]
        r = self.run("probe", timeout_s=spec["timeout_s"] + pts * spec.get("timeout_per_point_s", 0.03),
                     start_khz=start, stop_khz=stop, step_khz=step_khz, **q)
        all_rows = r.get("rows", [])
        rows = [x for x in all_rows if x["avg_dbm"] is not None and not (x["err_rx"] & 0x0040)]
        # Critical: DO NOT discard PLL failure rows before deciding whether the sweep locked.
        # A boundary sweep may have valid RSSI at some points and no RSSI at failed points.
        locked = bool(all_rows) and not any(x["err_rx"] & 0x0040 for x in all_rows)
        complete = bool(r.get("ok") and r.get("_done") and len(all_rows) == pts)
        if not rows or not locked or not complete:
            return {"detected": False, "locked": locked, "raw_ok": False, "snr_db": None, "level_db": None,
                    "offset_hz": None, "noise_db": None, "peaks": [], "image_db": None, "image_lower_bound": False,
                    "rbw_hz": q.get("bw"), "units": "dBm (RSSI, uncalibrated)",
                    "note": "rejected incomplete/no-lock sweep: %d/%d rows, %d RSSI, restore=%s done=%s" %
                    (len(all_rows), pts, len(rows), r.get("restore"), r.get("_done"))}
        vals = sorted(x["avg_dbm"] for x in rows)
        floor = vals[len(vals) // 2]
        peaks = sorted(((x["khz"] * 1000 - tune_hz, x["avg_dbm"] - floor) for x in rows), key=lambda p: -p[1])
        # collapse neighbouring steps into one peak per bandwidth
        bw = q.get("bw", 4800)
        merged = []
        for o, d in peaks:
            if all(abs(o - m) > bw for m, _ in merged):
                merged.append((o, round(d, 2)))
        res = self._result_from_peaks(merged[:8], floor, bw, expect, window if window > 0 else 0, False,
                                      "dBm (RSSI, 0.5 dB steps)", locked,
                                      "RSSI sweep: offset resolution = step; floor clamps at -127.5 dBm")
        res["image_db"] = None
        res["note"] += "; RSSI sweep searches absolute RF steps: moving the nominal centre alone " \
                       "does not independently validate LO retune; image rejection N/A"
        return res

    def _measure_heltec_sweep(self, tune_hz, expect, window, start_hz, stop_hz, step_hz, points):
        dwell_ms = int(self.params.get("dwell_ms", 20))
        rows = []
        for hz in range(start_hz, stop_hz + 1, step_hz):
            r = self.run("probe", freq_hz=hz, dwell_ms=dwell_ms)
            rows.append({"hz": hz, "r": r})
        all_rows = [x["r"] for x in rows]
        locked = bool(all_rows) and all(x.get("ok") and not (x.get("errors", 0) & 0x0040)
                                        for x in all_rows)
        complete = len(rows) == points and all(x.get("_done") for x in all_rows)
        if not rows or not locked or not complete:
            return {"detected": False, "locked": locked, "raw_ok": False, "snr_db": None,
                    "level_db": None, "offset_hz": None, "noise_db": None, "peaks": [],
                    "image_db": None, "image_lower_bound": False, "rbw_hz": step_hz,
                    "units": "dBm (SX1262 instantaneous RSSI, uncalibrated)",
                    "note": "rejected incomplete/no-lock Heltec sweep: %d/%d rows" % (len(rows), points)}
        vals = [x["r"]["rssi_dbm"] for x in rows]
        floor = sorted(vals)[len(vals) // 2]
        peaks = sorted(((x["hz"] - tune_hz, x["r"]["rssi_dbm"] - floor) for x in rows),
                       key=lambda p: -p[1])
        merged = []
        for offset, db in peaks:
            if all(abs(offset - previous) > max(step_hz, 4800) for previous, _ in merged):
                merged.append((offset, round(db, 2)))
        res = self._result_from_peaks(merged[:8], floor, step_hz, expect, window, False,
                                      "dBm (SX1262 RSSI, uncalibrated)", locked,
                                      "instantaneous RSSI sweep; no I/Q; absolute frequencies")
        res["image_db"] = None
        return res

    def close(self):
        self.t.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile", default="lakeshark_sx1262")
    ap.add_argument("--port")
    ap.add_argument("--serial-number")
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--list", action="store_true", help="list profiles and their command templates")
    ap.add_argument("--raw", help="send one raw console line (real board only) and print the reply")
    ap.add_argument("--tune", type=float, help="measure at this frequency (Hz), report peaks")
    a = ap.parse_args(argv)
    if a.list:
        for k, v in load_profiles().items():
            print("%-22s %-7s %-11s %s" % (k, v["chip"], v["kind"], v["status"]))
            for c, s in v["commands"].items():
                if s:
                    print("    %-8s %s" % (c, s["template"]))
        return 0
    bench = None
    if a.sim:
        from sim import SimBench
        bench = SimBench(chip=load_profiles()[a.profile]["chip"])
    dut = Dut(a.profile, a.port, a.serial_number, bench)
    try:
        if a.raw:
            raw, done = dut.t.exchange(a.raw, r"(?!x)x", 3)  # read for 3 s
            print(raw)
        elif a.tune:
            print(json.dumps(dut.measure(a.tune, 0, 0, image=False), indent=2, default=str))
        else:
            print(json.dumps(dut.info(), indent=2, default=str))
    finally:
        dut.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
