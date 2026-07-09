#!/usr/bin/env nextflow
// ============================================================================
//  bagASM — fungal genome assembly pipeline
//
//  Short reads only:
//    fastp -> SPAdes -> GetOrganelle (mitogenome, assembly-graph w/ read-based
//    fallback) -> Redundans -> chlomito -> Polypolish -> rename/sort
//
//  Long reads (--lr/--lr_type) present:
//    Flye -> GetOrganelle (mitogenome, from Flye's .gfa) -> polish -> rename/sort
//    polishing: Polypolish if short reads are also given, else medaka (ont),
//    racon (pacbio-clr), or none (pacbio-hifi is already highly accurate)
//    Redundans/chlomito are skipped in this branch: Flye assemblies are
//    already long-read-scaffolded, and organelle decontamination was not
//    requested for this path.
//
//  Nextflow DSL2
// ============================================================================

nextflow.enable.dsl = 2

// Modules used in both branches are aliased for the long-read (_LR) branch:
// DSL2 forbids invoking the same process name twice in one workflow, even
// across mutually-exclusive if/else branches.
include { FASTP                       } from './modules/fastp'
include { SPADES                      } from './modules/spades'
include { FLYE                        } from './modules/flye'
include { GET_ORGANELLE_SETUP         } from './modules/get_organelle_setup'
include { GET_ORGANELLE_FROM_ASSEMBLY                                  } from './modules/get_organelle_from_assembly'
include { GET_ORGANELLE_FROM_ASSEMBLY as GET_ORGANELLE_FROM_ASSEMBLY_LR } from './modules/get_organelle_from_assembly'
include { GET_ORGANELLE_FROM_READS    } from './modules/get_organelle_from_reads'
include { FINALIZE_MITOGENOME                          } from './modules/finalize_mitogenome'
include { FINALIZE_MITOGENOME as FINALIZE_MITOGENOME_LR } from './modules/finalize_mitogenome'
include { REDUNDANS                   } from './modules/redundans'
include { CHLOMITO                    } from './modules/chlomito'
include { POLYPOLISH                            } from './modules/polypolish'
include { POLYPOLISH as POLYPOLISH_LR           } from './modules/polypolish'
include { MEDAKA                      } from './modules/medaka'
include { RACON                       } from './modules/racon'
include { RENAME_SORT                          } from './modules/rename_sort'
include { RENAME_SORT as RENAME_SORT_LR        } from './modules/rename_sort'

def helpMessage() {
    log.info """
  ${'-' * 72}
  bagASM — fungal genome assembly pipeline
  ${'-' * 72}
  USAGE (short reads only):
    nextflow run main.nf --r1 R1.fq.gz --r2 R2.fq.gz --strain StrainID --outdir results

  USAGE (long reads, optionally with short reads for polishing):
    nextflow run main.nf --lr reads.fq.gz --lr_type ont [--r1 R1.fq.gz --r2 R2.fq.gz] \\
        --strain StrainID --outdir results

  REQUIRED
    --strain           Strain/sample ID used for output naming
    --outdir           Output directory
    --r1 / --r2        Illumina paired reads (required unless --lr is given)
    --lr               Long-read FASTQ(.gz) (PacBio/ONT); switches assembler to Flye
    --lr_type          Required with --lr: ont | pacbio-clr | pacbio-hifi

  MULTIPLE LANES/RUNS OF THE SAME LIBRARY
    Pass a comma-separated list to --r1/--r2/--lr to pool several lanes or
    runs of one library, e.g.:
      --r1 L001_R1.fq.gz,L002_R1.fq.gz --r2 L001_R2.fq.gz,L002_R2.fq.gz
    --r1 and --r2 must list the same number of files, in matching lane order.
    This is for multiple lanes/runs of the SAME library, not distinct library
    preps (different insert sizes, mixed PE/MP) — those aren't supported.

  OPTIONAL
    --threads                     Threads for process_high steps [${params.threads}]
    --chlomito_mito_alcr_cutoff    chlomito mitochondrial ALCR cutoff [${params.chlomito_mito_alcr_cutoff}] (short-read path only)
    --chlomito_mito_sdr_cutoff     chlomito mitochondrial SDR cutoff [${params.chlomito_mito_sdr_cutoff}] (short-read path only)
    --ont_mode                     Flye ONT preset [${params.ont_mode}]: hq (--nano-hq, modern/Dorado-Guppy-sup)
                                   | raw (--nano-raw, R9/low-quality basecalls)  (--lr_type ont only)
    --medaka_model                 Override medaka's auto-detected model (--lr_type ont only)
    --polish_rounds                 Number of minibwa+Polypolish iterations [${params.polish_rounds}]
    --max_memory                   Override memory cap for process_high/long steps

  NOTE: Nextflow reserves single-dash options for its own launcher flags, so
  inputs are passed as --r1/--r2/--lr (double-dash) rather than the -1/-2
  convention used by tools like bwa/samtools.
  ${'-' * 72}
  """.stripIndent()
}

if (params.help) {
    helpMessage()
    exit 0
}

if (!params.strain || !params.outdir) {
    log.error "Missing --strain or --outdir. Use --help for usage."
    exit 1
}

def has_sr = params.r1 && params.r2
def has_lr = params.lr as boolean

if (!has_sr && !has_lr) {
    log.error "Provide either --r1/--r2, or --lr (with --lr_type). Use --help for usage."
    exit 1
}
if (has_lr && !(params.lr_type in ['ont', 'pacbio-clr', 'pacbio-hifi'])) {
    log.error "--lr_type must be one of: ont, pacbio-clr, pacbio-hifi"
    exit 1
}
if (!(params.ont_mode in ['hq', 'raw'])) {
    log.error "--ont_mode must be one of: hq, raw"
    exit 1
}
if (!(params.polish_rounds instanceof Integer) || params.polish_rounds < 1) {
    log.error "--polish_rounds must be a positive integer"
    exit 1
}

// Comma-separated lists pool multiple lanes/runs of the same library.
def splitFiles = { p -> p.toString().split(',').collect { file(it.trim()) } }

def r1_files = has_sr ? splitFiles(params.r1) : []
def r2_files = has_sr ? splitFiles(params.r2) : []
if (has_sr && r1_files.size() != r2_files.size()) {
    log.error "--r1 and --r2 must list the same number of files (${r1_files.size()} vs ${r2_files.size()})"
    exit 1
}
def lr_files = has_lr ? splitFiles(params.lr) : []

workflow {

    // Downloaded once into params.getorganelle_db and cached across runs
    // (storeDir); every mitogenome-extraction call below depends on it.
    GET_ORGANELLE_SETUP()

    ch_trimmed = Channel.empty()
    if (has_sr) {
        ch_reads = Channel.of(tuple(params.strain, r1_files, r2_files))
        FASTP(ch_reads)
        ch_trimmed = FASTP.out.reads
    }

    if (has_lr) {
        // ── Long-read assembly branch ──────────────────────────────────────
        ch_lr = Channel.of(tuple(params.strain, lr_files, params.lr_type))
        FLYE(ch_lr)

        GET_ORGANELLE_FROM_ASSEMBLY_LR(FLYE.out.graph, GET_ORGANELLE_SETUP.out.label_db)
        FINALIZE_MITOGENOME_LR(
            GET_ORGANELLE_FROM_ASSEMBLY_LR.out.result
                .map { strain, fasta, n_seqs -> tuple(strain, fasta) }
        )

        ch_lr_reads = ch_lr.map { strain, lr, type -> tuple(strain, lr) }

        ch_lr_final = Channel.empty()
        if (has_sr) {
            POLYPOLISH_LR(FLYE.out.assembly.join(ch_trimmed.map { strain, r1, r2 -> tuple(strain, r1, r2) }))
            ch_lr_final = POLYPOLISH_LR.out.fasta
        } else if (params.lr_type == 'ont') {
            MEDAKA(FLYE.out.assembly.join(ch_lr_reads))
            ch_lr_final = MEDAKA.out.fasta
        } else if (params.lr_type == 'pacbio-clr') {
            RACON(FLYE.out.assembly.join(ch_lr_reads))
            ch_lr_final = RACON.out.fasta
        } else {
            // pacbio-hifi, no short reads: Flye's own consensus is already
            // highly accurate, so no extra polishing pass is applied.
            ch_lr_final = FLYE.out.assembly
        }
        RENAME_SORT_LR(ch_lr_final)

    } else {
        // ── Short-read-only assembly branch ────────────────────────────────
        SPADES(ch_trimmed)

        // Mitogenome extraction: fast assembly-graph attempt first, falling
        // back to the slower read-based extension if not a single scaffold.
        GET_ORGANELLE_FROM_ASSEMBLY(SPADES.out.graph, GET_ORGANELLE_SETUP.out.label_db)

        ch_goa = GET_ORGANELLE_FROM_ASSEMBLY.out.result
            .map { strain, fasta, n_seqs -> tuple(strain, fasta, n_seqs.trim().toInteger()) }
            .branch {
                single: it[2] == 1
                multi:  it[2] != 1
            }

        ch_goa_single = ch_goa.single.map { strain, fasta, n -> tuple(strain, fasta) }

        GET_ORGANELLE_FROM_READS(
            ch_goa.multi
                .map { strain, fasta, n -> strain }
                .join(ch_trimmed.map { strain, r1, r2 -> tuple(strain, r1, r2) }),
            GET_ORGANELLE_SETUP.out.label_db,
            GET_ORGANELLE_SETUP.out.seed_db
        )

        FINALIZE_MITOGENOME(ch_goa_single.mix(GET_ORGANELLE_FROM_READS.out.fasta))

        // Nuclear assembly refinement: scaffold/gapfill, decontaminate, polish
        REDUNDANS(SPADES.out.scaffolds.join(ch_trimmed.map { strain, r1, r2 -> tuple(strain, r1, r2) }))
        CHLOMITO(REDUNDANS.out.scaffolds.join(ch_trimmed.map { strain, r1, r2 -> tuple(strain, r1, r2) }))

        ch_for_polish = CHLOMITO.out.decontaminated
            .join(ch_trimmed.map { strain, r1, r2 -> tuple(strain, r1, r2) })
        POLYPOLISH(ch_for_polish)

        RENAME_SORT(POLYPOLISH.out.fasta)
    }
}
