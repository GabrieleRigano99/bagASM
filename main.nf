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

// GetOrganelle's own -F/-a organelle-type vocabulary (get_organelle_from_assembly.py,
// get_organelle_from_reads.py, get_organelle_config.py); "anonym" is deliberately
// excluded since it requires extra custom seed/gene-fasta parameters this
// pipeline doesn't expose.
GETORGANELLE_TYPES = ['embplant_pt', 'embplant_mt', 'embplant_nr', 'fungus_mt', 'fungus_nr', 'animal_mt', 'other_pt']

// ── Help message ─────────────────────────────────────────────────────────────
def helpMessage() {
    def R  = "[0m"       // reset
    def B  = "[1m"       // bold
    def DM = "[2m"       // dim
    def GR = "[1;32m"    // bold green
    def CY = "[1;36m"    // bold cyan
    def YL = "[1;33m"    // bold yellow
    def MG = "[1;35m"    // bold magenta
    def LN = "${CY}${'─' * 72}${R}"   // section divider

    log.info """
${GR}   _                    _    ____  __  __ ${R}
${GR}  | |__   __ _  __ _   / \\  / ___||  \\/  |${R}
${GR}  | '_ \\ / _' |/ _' | / _ \\ \\___ \\| |\\/| |${R}
${GR}  | |_) | (_| | (_| |/ ___ \\ ___) | |  | |${R}
${GR}  |_.__/ \\__,_|\\__, /_/   \\_\\____/|_|  |_|${R}
${GR}               |___/${R}

  ${B}bagASM${R} — fungal genome assembly pipeline
  ${DM}Version 1.0.0  •  Bioinformatics and Computational Genomics LAB, UniME${R}
  ${DM}Main Developer  •  Gabriele Rigano - ORCID https://orcid.org/0009-0008-1928-6789 ${R}

  ${B}USAGE:${R}  nextflow run main.nf [options]

${LN}
  ${CY}${B}MODE 1${R}  —  short reads only
${LN}

  ${DM}fastp -> SPAdes -> GetOrganelle -> Redundans -> chlomito -> Polypolish -> rename/sort${R}

    nextflow run main.nf --r1 R1.fq.gz --r2 R2.fq.gz --strain StrainID --outdir results

  ${YL}${B}REQUIRED${R}
    ${B}--r1 / --r2${R}          Illumina paired reads (fastq/fastq.gz)
    ${B}--strain${R}             Strain/sample ID used for output naming
    ${B}--outdir${R}             Output directory

${LN}
  ${CY}${B}MODE 2${R}  —  long reads only  ${DM}(PacBio/ONT; switches assembler to Flye)${R}
${LN}

  ${DM}Flye -> GetOrganelle -> polish -> rename/sort${R}
  ${DM}polisher is chosen automatically from --lr_type:${R}
    ${DM}ont          -> medaka${R}
    ${DM}pacbio-clr   -> racon${R}
    ${DM}pacbio-hifi  -> none  ${DM}(Flye's own consensus is already highly accurate)${R}

    nextflow run main.nf --lr reads.fq.gz --lr_type ont --strain StrainID --outdir results

  ${YL}${B}REQUIRED${R}
    ${B}--lr${R}                 Long-read FASTQ(.gz)
    ${B}--lr_type${R}            ${MG}ont${R} | ${MG}pacbio-clr${R} | ${MG}pacbio-hifi${R}
    ${B}--strain${R} / ${B}--outdir${R}   as in MODE 1

${LN}
  ${CY}${B}MODE 3${R}  —  long reads + short reads  ${DM}(short reads polish instead)${R}
${LN}

  ${DM}Same as MODE 2 through Flye/mitogenome extraction, but --r1/--r2 (if given)${R}
  ${DM}always override medaka/racon with Polypolish, regardless of --lr_type.${R}

    nextflow run main.nf --lr reads.fq.gz --lr_type ont \\
        --r1 R1.fq.gz --r2 R2.fq.gz --strain StrainID --outdir results

${LN}
  ${YL}${B}MULTIPLE LANES/RUNS OF THE SAME LIBRARY${R}
${LN}

  Pass a comma-separated list to ${B}--r1${R}/${B}--r2${R}/${B}--lr${R} to pool several lanes or
  runs of one library, e.g.:
    --r1 L001_R1.fq.gz,L002_R1.fq.gz --r2 L001_R2.fq.gz,L002_R2.fq.gz
  --r1 and --r2 must list the same number of files, in matching lane order.
  ${DM}This is for multiple lanes/runs of the SAME library, not distinct library${R}
  ${DM}preps (different insert sizes, mixed PE/MP) — those aren't supported.${R}

${LN}
  ${YL}${B}OPTIONAL${R}
${LN}

    ${B}--species${R}            Organelle type to extract [${params.species}], passed to
                        GetOrganelle's -F/-a. One of:
                          ${MG}${GETORGANELLE_TYPES.join(' | ')}${R}
                        or several joined by comma, e.g. embplant_pt,embplant_mt
    ${B}--threads${R}            Threads for process_high steps [${params.threads}]
    ${B}--chlomito_mito_alcr_cutoff${R}  chlomito mitochondrial ALCR cutoff [${params.chlomito_mito_alcr_cutoff}]  ${DM}(MODE 1 only)${R}
    ${B}--chlomito_mito_sdr_cutoff${R}   chlomito mitochondrial SDR cutoff [${params.chlomito_mito_sdr_cutoff}]  ${DM}(MODE 1 only)${R}
    ${B}--ont_mode${R}            Flye ONT preset [${params.ont_mode}]: ${MG}hq${R} (--nano-hq, modern/Dorado-Guppy-sup)
                        | ${MG}raw${R} (--nano-raw, R9/low-quality basecalls)  ${DM}(--lr_type ont only)${R}
    ${B}--flye_genome_size${R}    Expected genome size, e.g. ${MG}35m${R} — Flye -g/--genome-size  ${DM}(long-read mode only)${R}
    ${B}--flye_asm_coverage${R}   Downsample to this per-base coverage for the initial disjointig
                        assembly — Flye --asm-coverage; requires --flye_genome_size
                        ${DM}(long-read mode only)${R}
    ${B}--medaka_model${R}        Override medaka's auto-detected model  ${DM}(--lr_type ont only)${R}
    ${B}--polish_rounds${R}       Number of minibwa+Polypolish iterations [${params.polish_rounds}]
    ${B}--max_memory${R}          Override memory cap for process_high/long steps

${LN}
  ${DM}NOTE: Nextflow reserves single-dash options for its own launcher flags, so${R}
  ${DM}inputs are passed as --r1/--r2/--lr (double-dash) rather than the -1/-2${R}
  ${DM}convention used by tools like bwa/samtools.${R}
${LN}
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
if (params.flye_asm_coverage && !params.flye_genome_size) {
    log.error "--flye_asm_coverage requires --flye_genome_size (Flye needs a genome size estimate to downsample coverage against)"
    exit 1
}
if (!(params.polish_rounds instanceof Integer) || params.polish_rounds < 1) {
    log.error "--polish_rounds must be a positive integer"
    exit 1
}
def species_tokens = params.species.toString().split(',').collect { it.trim() }
def bad_species = species_tokens - GETORGANELLE_TYPES
if (bad_species) {
    log.error "--species has invalid value(s) ${bad_species}. Must be one of: ${GETORGANELLE_TYPES.join(', ')} (or several joined by comma)"
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
