#!/usr/bin/env python3
"""Combines QUAST, Qualimap bamqc, and (optionally) compleasm output for one
strain's final assembly into a single human-readable Markdown report.

Each tool writes its own report in its own format inside its own output
directory (QUAST: <dir>/report.tsv; Qualimap: <dir>/genome_results.txt;
compleasm: <dir>/summary.txt). This just pulls the handful of headline
metrics out of each and lays them out together, so there's one file to
glance at per strain instead of three.
"""
import argparse
import re
import sys
from pathlib import Path

# QUAST report.tsv rows worth surfacing, in display order. Metric names must
# match QUAST's own labels exactly (confirmed against real report.tsv output,
# QUAST 5.3.0) — this pipeline's QUAST module always runs single-assembly
# (-l <strain>), so report.tsv has exactly one metric-name column plus one
# value column.
QUAST_METRICS = [
    "# contigs",
    "Largest contig",
    "Total length",
    "GC (%)",
    "N50",
    "N90",
    "L50",
    "# N's per 100 kbp",
]

QUALIMAP_PATTERNS = {
    "Reads": r"number of reads = ([\d,]+)",
    "Mapped reads": r"number of mapped reads = ([\d,]+ \([\d.]+%\))",
    "Mean coverage": r"mean coverageData = ([\d.]+X)",
    "Mean mapping quality": r"mean mapping quality = ([\d.]+)",
    "Mean insert size": r"mean insert size = ([\d.]+)",
    "Duplication rate": r"duplication rate = ([\d.]+%)",
    "GC content": r"GC percentage = ([\d.]+%)",
}


def parse_quast(report_dir):
    report_tsv = Path(report_dir) / "report.tsv"
    if not report_tsv.is_file():
        return None
    values = {}
    with open(report_tsv) as fh:
        for line in fh:
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 2:
                values[fields[0]] = fields[1]
    return {metric: values[metric] for metric in QUAST_METRICS if metric in values}


def parse_qualimap(report_dir):
    results_txt = Path(report_dir) / "genome_results.txt"
    if not results_txt.is_file():
        return None
    text = results_txt.read_text()
    metrics = {}
    for label, pattern in QUALIMAP_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            metrics[label] = match.group(1)
    return metrics


def parse_compleasm(report_dir):
    if report_dir is None:
        return None
    summary_txt = Path(report_dir) / "summary.txt"
    if not summary_txt.is_file():
        return None
    text = summary_txt.read_text()
    lineage_match = re.search(r"## lineage:\s*(\S+)", text)
    metrics = {"Lineage": lineage_match.group(1) if lineage_match else "unknown"}
    labels = {"S": "Single", "D": "Duplicated", "F": "Fragmented", "I": "Interspersed", "M": "Missing"}
    for code, label in labels.items():
        match = re.search(rf"^{code}:([\d.]+%), (\d+)$", text, re.MULTILINE)
        if match:
            metrics[label] = f"{match.group(1)} ({match.group(2)})"
    total_match = re.search(r"^N:(\d+)$", text, re.MULTILINE)
    if total_match:
        metrics["Total BUSCOs"] = total_match.group(1)
    return metrics


def render_table(metrics):
    lines = ["| Metric | Value |", "|---|---|"]
    for key, value in metrics.items():
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strain", required=True)
    parser.add_argument("--quast-dir", required=True)
    parser.add_argument("--qualimap-dir", required=True)
    parser.add_argument("--compleasm-dir", default=None, help="omit or pass a non-existent path if compleasm didn't run")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    quast_metrics = parse_quast(args.quast_dir)
    qualimap_metrics = parse_qualimap(args.qualimap_dir)
    compleasm_metrics = parse_compleasm(args.compleasm_dir)

    sections = [f"# Final assembly QC report — {args.strain}\n"]

    if quast_metrics:
        sections.append("## Assembly contiguity (QUAST)\n\n" + render_table(quast_metrics) + "\n")
    else:
        sections.append("## Assembly contiguity (QUAST)\n\n_report.tsv not found._\n")

    if compleasm_metrics:
        sections.append("## Gene completeness (compleasm)\n\n" + render_table(compleasm_metrics) + "\n")

    if qualimap_metrics:
        sections.append("## Read-mapping stats (Qualimap bamqc)\n\n" + render_table(qualimap_metrics) + "\n")
    else:
        sections.append("## Read-mapping stats (Qualimap bamqc)\n\n_genome_results.txt not found._\n")

    Path(args.output).write_text("\n".join(sections))


if __name__ == "__main__":
    main()
