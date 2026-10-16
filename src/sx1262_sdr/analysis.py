"""Parse LakeShark sxprobe output; status/RSSI is not proof of RF reception."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import csv
import json

PLL_LOCK_ERROR = 0x0040
IMAGE_CAL_ERROR = 0x0010
EXPECTED_HEADER = ("sxp", "khz", "err_cal", "err_rx", "st_cal", "st_rx",
                   "n", "avg_dbm", "max_dbm", "min_dbm", "us")


@dataclass(frozen=True)
class Row:
    frequency_khz: int
    err_cal: int
    err_rx: int
    st_cal: int
    st_rx: int
    reads: int
    avg_dbm: float | None
    max_dbm: float | None
    min_dbm: float | None
    elapsed_us: int

    @property
    def pll_error(self) -> bool:
        return bool(self.err_rx & PLL_LOCK_ERROR)

    @property
    def image_cal_error(self) -> bool:
        return bool(self.err_cal & IMAGE_CAL_ERROR)

    @property
    def status(self) -> str:
        if self.pll_error:
            return "rx_pll_error"
        if self.reads == 0:
            return "no_rssi_readings"
        if self.avg_dbm is None:
            return "incomplete_rssi"
        return "rssi_observed_unverified"

    def to_dict(self) -> dict:
        return dict(frequency_khz=self.frequency_khz,
                    frequency_mhz=self.frequency_khz / 1000.0,
                    err_cal=f"{self.err_cal:04X}", err_rx=f"{self.err_rx:04X}",
                    st_cal=f"{self.st_cal:02X}", st_rx=f"{self.st_rx:02X}",
                    reads=self.reads, avg_dbm=self.avg_dbm,
                    max_dbm=self.max_dbm, min_dbm=self.min_dbm,
                    elapsed_us=self.elapsed_us,
                    pll_error=self.pll_error,
                    image_cal_error=self.image_cal_error,
                    classification=self.status,
                    rf_reception_proven=False)


def parse_sxp(text: str) -> list[Row]:
    data = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip().startswith("sxp,"):
            continue
        cols = next(csv.reader([line]))
        if len(cols) != len(EXPECTED_HEADER):
            raise ValueError(f"line {lineno}: expected {len(EXPECTED_HEADER)} columns, got {len(cols)}")
        if tuple(c.strip() for c in cols) == EXPECTED_HEADER:
            continue
        try:
            a = [c.strip() for c in cols]
            freq = int(a[1])
            ec, er = int(a[2], 16), int(a[3], 16)
            sc, sr = int(a[4], 16), int(a[5], 16)
            reads, elapsed = int(a[6]), int(a[10])
            if not (0 <= freq <= 4_095_000 and 0 <= ec <= 65535 and
                    0 <= er <= 65535 and 0 <= sc <= 255 and 0 <= sr <= 255
                    and 0 <= reads <= 64 and elapsed >= 0):
                raise ValueError("out-of-range fields")
            nums = [float(c) if c else None for c in a[7:10]]
            if reads and any(n is None for n in nums):
                raise ValueError("positive read count with absent RSSI values")
            if not reads and any(n is not None for n in nums):
                raise ValueError("zero read count with RSSI values")
            data.append(Row(freq, ec, er, sc, sr, reads, *nums, elapsed))
        except (ValueError, IndexError) as ex:
            raise ValueError(f"line {lineno}: invalid SXPROBE row: {ex}") from ex
    if not data:
        raise ValueError("no SXPROBE data rows found")
    return data


def analyze(text: str, source: str = "unspecified", origin: str = "unverified") -> dict:
    rows = parse_sxp(text)
    counts = Counter(r.status for r in rows)
    return dict(schema_version=1, data_origin=origin, input_source=source,
                interpretation="Device status/RSSI only. No independently tracked RF tone evidence.",
                rf_reception_proven=False, data_points=len(rows),
                status_counts=dict(sorted(counts.items())),
                rows=[r.to_dict() for r in rows])


def dump_json(result: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"will not overwrite existing output: {path}")
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
