#!/usr/bin/env python3
"""Native long-read organelle-contamination filter.

Reimplements chlomito's two-metric approach (ALCR + SDR) for long reads,
since chlomito itself has no long-read input mode (it requires paired
short reads for its depth-ratio metric). A contig is flagged as organelle
contamination only when BOTH of these clear their cutoff:

  ALCR (alignment length coverage ratio): fraction of the contig's length
  that aligns to the extracted organelle reference. Low ALCR protects
  contigs that only contain a short organelle-derived fragment (e.g. from
  horizontal gene transfer into the nuclear genome) from being flagged.

  SDR (sequencing depth ratio): the contig's mean long-read depth divided
  by the organelle reference's own mean long-read depth. Organelles exist
  in many copies per cell, so true organelle contigs should sit close to
  the organelle reference's depth; nuclear contigs should not.
"""
import argparse
import subprocess
import sys
from collections import defaultdict


def run(cmd):
    subprocess.run(cmd, shell=True, check=True)


def read_fasta_lengths(path):
    lengths = {}
    name = None
    length = 0
    with open(path) as f:
        for line in f:
            if line.startswith(">"):
                if name is not None:
                    lengths[name] = length
                name = line[1:].split()[0]
                length = 0
            else:
                length += len(line.strip())
    if name is not None:
        lengths[name] = length
    return lengths


def read_fasta_records(path):
    """Yield (name, header_line, sequence_lines) preserving original formatting."""
    name = None
    header = None
    seq_lines = []
    with open(path) as f:
        for line in f:
            if line.startswith(">"):
                if name is not None:
                    yield name, header, seq_lines
                name = line[1:].split()[0]
                header = line.rstrip("\n")
                seq_lines = []
            else:
                seq_lines.append(line)
    if name is not None:
        yield name, header, seq_lines


def merged_aligned_length(intervals):
    """Merge overlapping (start, end) intervals and sum their total length,
    so a contig with multiple overlapping partial hits isn't double-counted."""
    if not intervals:
        return 0
    intervals = sorted(intervals)
    total = 0
    cur_start, cur_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = start, end
    total += cur_end - cur_start
    return total


def compute_alcr(paf_path, contig_lengths):
    hits = defaultdict(list)
    with open(paf_path) as f:
        for line in f:
            fields = line.rstrip("\n").split("\t")
            query, q_start, q_end = fields[0], int(fields[2]), int(fields[3])
            hits[query].append((q_start, q_end))
    alcr = {}
    for contig, length in contig_lengths.items():
        aligned = merged_aligned_length(hits.get(contig, []))
        alcr[contig] = aligned / length if length else 0.0
    return alcr


def compute_depth(bam_path, threads):
    run(f"samtools index -@ {threads} {bam_path}")
    out = subprocess.run(
        f"samtools coverage {bam_path}", shell=True, check=True,
        capture_output=True, text=True,
    ).stdout
    depth = {}
    for line in out.splitlines():
        if line.startswith("#"):
            continue
        fields = line.split("\t")
        rname, meandepth = fields[0], float(fields[6])
        depth[rname] = meandepth
    return depth


def reference_mean_depth(depth_by_seq, seq_lengths):
    """Length-weighted mean depth across all sequences in a (possibly
    multi-sequence) reference, so a multi-contig organelle reference is
    handled correctly too."""
    total_len = sum(seq_lengths.values())
    if total_len == 0:
        return 0.0
    weighted = sum(depth_by_seq.get(name, 0.0) * length for name, length in seq_lengths.items())
    return weighted / total_len


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--assembly", required=True)
    p.add_argument("--mito-ref", required=True)
    p.add_argument("--reads-vs-assembly-bam", required=True)
    p.add_argument("--reads-vs-mito-bam", required=True)
    p.add_argument("--contigs-vs-mito-paf", required=True)
    p.add_argument("--alcr-cutoff", type=float, required=True)
    p.add_argument("--sdr-cutoff", type=float, required=True)
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--output-fasta", required=True)
    p.add_argument("--output-report", required=True)
    args = p.parse_args()

    contig_lengths = read_fasta_lengths(args.assembly)
    mito_lengths = read_fasta_lengths(args.mito_ref)

    alcr = compute_alcr(args.contigs_vs_mito_paf, contig_lengths)
    contig_depth = compute_depth(args.reads_vs_assembly_bam, args.threads)
    mito_depth_by_seq = compute_depth(args.reads_vs_mito_bam, args.threads)
    mito_depth = reference_mean_depth(mito_depth_by_seq, mito_lengths)

    flagged = set()
    with open(args.output_report, "w") as report:
        report.write("contig\tlength\talcr\tdepth\tmito_depth\tsdr\tflagged_as_organelle\n")
        for contig, length in contig_lengths.items():
            depth = contig_depth.get(contig, 0.0)
            sdr = depth / mito_depth if mito_depth else 0.0
            is_flagged = alcr[contig] >= args.alcr_cutoff and sdr >= args.sdr_cutoff
            if is_flagged:
                flagged.add(contig)
            report.write(
                f"{contig}\t{length}\t{alcr[contig]:.4f}\t{depth:.2f}\t"
                f"{mito_depth:.2f}\t{sdr:.4f}\t{is_flagged}\n"
            )

    n_kept = 0
    with open(args.output_fasta, "w") as out:
        for name, header, seq_lines in read_fasta_records(args.assembly):
            if name in flagged:
                continue
            n_kept += 1
            out.write(header + "\n")
            out.writelines(seq_lines)

    sys.stderr.write(
        f"[decontam_organelle_lr] {len(flagged)} of {len(contig_lengths)} contigs "
        f"flagged as organelle contamination and removed; {n_kept} contigs kept.\n"
    )


if __name__ == "__main__":
    main()
