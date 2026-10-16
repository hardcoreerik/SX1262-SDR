# SPDX-License-Identifier: GPL-3.0-only
# Part of the SX1262-SDR bench harness. Credits: see harness/README.md.
"""Pass/fail-by-frequency chart and SNR/MDS plots for one results folder.

usage: python plot_results.py results/<run_id>
Writes pass_fail.png (and mds.png when MDS was measured) next to summary.csv.
"""
from __future__ import annotations

import csv
import json
import os
import sys


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def plot(run_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with open(os.path.join(run_dir, "summary.csv"), newline="") as fh:
        summ = list(csv.DictReader(fh))
    with open(os.path.join(run_dir, "measurements.csv"), newline="") as fh:
        meas = list(csv.DictReader(fh))
    meta = {}
    if os.path.exists(os.path.join(run_dir, "meta.json")):
        with open(os.path.join(run_dir, "meta.json")) as fh:
            meta = json.load(fh)
    snr_min = meta.get("config", {}).get("pass", {}).get("snr_min_db", 10.0)
    labels = ["%g" % float(s["freq_mhz"]) for s in summ]
    colors = {"PASS": "#2e7d32", "FAIL": "#c62828", "UNVERIFIED": "#f9a825"}
    x = list(range(len(summ)))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(max(8, 0.8 * len(summ) + 3), 7), sharex=True)
    ax1.bar(x, [max(float(s["pass_fraction"]), 0.03) for s in summ], color=[colors.get(s["verdict"], "grey") for s in summ])
    ax1.axhline(float(meta.get("config", {}).get("pass", {}).get("freq_pass_fraction", 0.8)), ls="--", c="k", lw=0.8)
    for i, s in enumerate(summ):
        ax1.text(i, 1.02, s["verdict"], ha="center", fontsize=7, rotation=90 if len(summ) > 14 else 0)
    ax1.set_ylim(0, 1.25)
    ax1.set_ylabel("pass fraction (reps)")
    title = "%s  %s %s" % (meta.get("run_id", os.path.basename(run_dir)), meta.get("dut", {}).get("chip", ""),
                            "(SIMULATED)" if meta.get("simulated") else "")
    ax1.set_title(title)
    for i, s in enumerate(summ):
        pts = [_f(m["snr_db"]) for m in meas if _f(m["freq_hz"]) == _f(s["freq_hz"])]
        pts = [p for p in pts if p is not None]
        ax2.scatter([i] * len(pts), pts, s=12, c=colors.get(s["verdict"], "grey"))
    ax2.axhline(snr_min, ls="--", c="k", lw=0.8, label="SNR threshold %g dB" % snr_min)
    ax2.set_ylabel("SNR (dB, every rep)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, rotation=45, ha="right")
    ax2.set_xlabel("test frequency (MHz)")
    ax2.legend(loc="best", fontsize=8)
    fig.tight_layout()
    out = os.path.join(run_dir, "pass_fail.png")
    fig.savefig(out, dpi=110)
    plt.close(fig)
    outs = [out]

    mds = [(_f(s["freq_mhz"]), _f(s.get("mds_input_median_dbm")), _f(s.get("mds_tx_gain_median_db"))) for s in summ]
    if any(m[1] is not None or m[2] is not None for m in mds):
        use_dbm = any(m[1] is not None for m in mds)
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot([m[0] for m in mds], [m[1] if use_dbm else m[2] for m in mds], "o-")
        ax.set_xscale("log")
        ax.set_xlabel("MHz")
        ax.set_ylabel("MDS input (dBm)" if use_dbm else "MDS as Pluto gain (dB, relative)")
        ax.set_title("Minimum detectable signal (SNR >= %g dB)%s" % (snr_min, "  SIMULATED" if meta.get("simulated") else ""))
        ax.grid(True, which="both", alpha=0.3)
        fig.tight_layout()
        p2 = os.path.join(run_dir, "mds.png")
        fig.savefig(p2, dpi=110)
        plt.close(fig)
        outs.append(p2)
    print("plots: " + ", ".join(outs))
    return outs


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    plot(sys.argv[1])
