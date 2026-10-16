"""Offline, receiver-only SX1262 sweep analyzer; execution-folder logging."""
from pathlib import Path
import argparse
import logging
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sx1262_sdr.analysis import analyze, dump_json


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify existing SX1262 status/RSSI rows.")
    ap.add_argument("input", type=Path, help="Existing sxprobe output/CSV")
    ap.add_argument("--out", type=Path, required=True, help="New JSON path; never overwrite")
    ap.add_argument("--origin", choices=("synthetic", "live_device", "imported_report",
                                         "unverified"), default="unverified")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(Path.cwd() / "SX1262-SDR.log",
                                                      encoding="utf-8"),
                                  logging.StreamHandler()])
    try:
        result = analyze(a.input.read_text(encoding="utf-8"), str(a.input), a.origin)
        dump_json(result, a.out)
    except (FileNotFoundError, ValueError, FileExistsError, OSError) as exc:
        logging.error("Analysis refused: %s", exc)
        return 1
    logging.info("Analyzed %d rows; classifications %s; output %s",
                 result["data_points"], result["status_counts"], a.out)
    logging.warning("NO RF reception proven: independent tone and controls still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
