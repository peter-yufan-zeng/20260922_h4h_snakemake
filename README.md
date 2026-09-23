# Mouse RNA-seq on h4h (mm10)

Adapted from [AN_WGS_script/run_rnaseq_mouse.snk](https://github.com/peter-yufan-zeng/AN_WGS_script/blob/c0fe2a982cd09a9e6cec956141f0dd0f066bcaa9/run_rnaseq_mouse.snk), upstream commit `c0fe2a982cd09a9e6cec956141f0dd0f066bcaa9`, using the supplied h4h Slurm guide and module/reference listings.

The workflow retains paired-end lane merging → FastQC → Trim Galore → STAR two-pass alignment → RSEM gene/isoform expression. It adds MultiQC and uses `FastQC`, `cutadapt`, `trim_galore`, `star`, `rsem`, `samtools`, and `multiqc` modules. Each tool job initializes the module system, purges inherited modules, and loads its configured module list. No containers, reference downloads, Niagara paths, or `REF_DIR`/`BBUFFER` environment variables are needed.

## Configure before running

1. Put this checkout under your group's `/cluster/projects/...` directory. Edit `config/h4h.yaml` and `config/samples.tsv` there.
2. Use **mm10** FASTA and a matching, uncompressed mm10 GTF. The default FASTA `/cluster/tools/data/genomes/mouse/bwa/mm10.fasta` is inferred from your listing and needs verification. The configured GTF is your supplied `/cluster/tools/data/genomes/mouse/mm10/iGenomes/Annotation/Genes/genes.gtf`. Do not mix the mm39 ScaleRNA files, mm9 files, or an Ensembl GTF using `1` with a UCSC FASTA using `chr1`.
3. Set `sjdb_overhang` to the maximum read length minus 1 (100 is the original workflow's value). Confirm `strandedness`: `none`, `forward`, or `reverse`; the original unstranded behavior remains the default.
4. Replace example FASTQ paths. The sheet accepts a literal-tab-separated TSV or comma-separated CSV with exactly `Sample,Fastq1,Fastq2` as headers. Repeat a sample name on multiple rows for multiple lanes; R1/R2 lane order is preserved. Files must be `.fastq.gz` or `.fq.gz`. Relative paths resolve from the project working directory.
5. Inspect `module avail` and `module show` on h4h, then preferably pin module versions in the YAML lists. The supplied names do not establish versions. `modules_init` defaults to `/etc/profile.d/modules.sh`; change it if your cluster uses a different initialization script. The workflow expects the original STAR 2.7-era options, Trim Galore's classic `--cores` interface (0.6.x), and RSEM's `--strandedness` interface (1.3.x). Verify compatibility with the available versions.

Preflight checks the supplied FASTA/GTF for missing contigs, out-of-range exon coordinates, and missing gene/transcript IDs. The files cannot be accessed from this local workspace, so run preflight on h4h before building indexes.

STAR and RSEM references are built separately from the **same FASTA/GTF**, under `work/reference/mm10`. Existing BWA/Bowtie/HISAT2 indexes are not STAR/RSEM indexes. The shared `/cluster/tools` tree is never an output destination. Use a new `index_dir` when changing annotation, assembly, or STAR version; do not reuse an index built by an incompatible STAR version.

## Load the workflow runner

Use the h4h modules **`python3/3.10.9`** and **`snakemake/7.3.8`**. No virtualenv, pip installation, or Internet-enabled node is needed for setup or analysis.

```bash
module load python3/3.10.9 snakemake/7.3.8
python --version
snakemake --version
```

The Slurm launcher loads both modules automatically. Its profile uses the Snakemake 7 cluster interface and does not work with Snakemake 8/9. Keep FASTQs, indexes, results, and analysis scratch in project storage. `requirements.txt` is retained only for optional local development/testing; it is not an installation step for h4h and does not describe the site's module dependencies.

## Validate and submit

The supplied guide says `/cluster/projects` is unavailable on login2 and analysis must run on compute nodes. Obtain an allocation (`salloc --partition=all --cpus-per-task=1 --mem=4G --time=01:00:00`, adding `--account` if required), enter the allocated node with `srun --pty bash -l`, and run the following there. Replace `YOUR_GROUP/YOUR_PROJECT` with the actual directory containing this checkout. Merely obtaining an allocation may leave your shell on the login node.

```bash
cd /cluster/projects/YOUR_GROUP/YOUR_PROJECT
module load python3/3.10.9 snakemake/7.3.8
mkdir -p logs work/tmp
export TMPDIR="$PWD/work/tmp" TMP="$PWD/work/tmp" TEMP="$PWD/work/tmp"
export XDG_CACHE_HOME="$PWD/work/cache"
set -o pipefail
python scripts/preflight.py 2>&1 | tee logs/preflight.log
snakemake -s run_rnaseq_mouse.snk --profile profiles/h4h --cores 8 --dry-run

# The launcher loads python3/3.10.9 and snakemake/7.3.8 automatically.
# If needed, export H4H_MODULES_INIT to the module initialization script path.
# If an account is required, export H4H_ACCOUNT and also pass --account to sbatch.
sbatch --chdir="$PWD" scripts/run_h4h.sh
```

`run_h4h.sh` repeats preflight and runs the Snakemake controller on a compute node. Tool jobs, including lane concatenation, are separately submitted to Slurm. The controller needs a shared filesystem and permission to submit jobs from compute nodes; verify this site capability on h4h. Its four-day walltime is adjustable up to the documented partition limit. Resume by submitting the launcher again after a controller timeout; check for orphaned child jobs before resubmitting. To stop the entire workflow, cancel both controller and its child jobs deliberately; killing only the controller does not guarantee cancellation of its submitted children.

To select a different YAML file, export `H4H_CONFIG=/absolute/path/to/config.yaml`; the launcher passes it to both preflight and Snakemake. Keep input/reference changes in that file so preflight validates the configuration actually used. The dry-run command specifies eight cores to display the intended thread counts (Snakemake 7 otherwise caps dry-run threads at one); real cluster submission uses each rule's thread request.

The Slurm account is optional: `H4H_ACCOUNT` applies to child jobs, while the controller account must be supplied to its `sbatch` command. Module versions and reference paths remain site-specific settings, not locally verified facts.

## Resource requests and results

| Step | CPUs | Memory (MB) | Minutes | Partition |
|---|---:|---:|---:|---|
| STAR index | 8 | 80000 | 240 | veryhimem |
| RSEM reference | 4 | 16000 | 240 | all |
| Lane merge, per mate | 1 | 1024 | 120 | all |
| FastQC | 2 | 4000 | 120 | all |
| Trim Galore | 6 | 8000 | 240 | all |
| STAR alignment | 8 | 48000 | 240 | himem |
| RSEM | 8 | 16000 | 240 | all |
| MultiQC | 1 | 4000 | 60 | all |

These are starting requests, not measured requirements for your samples. STAR indexing retains the original 80 GB request and therefore uses `veryhimem`; alignment uses `himem`. All jobs request one node, one task, and `--cpus-per-task`, plus explicit total memory and walltime. Trim Galore uses `--cores 1` within a six-CPU allocation to leave room for its helper processes. Confirm current partition limits with `sinfo`; documented limits are checked by `scripts/slurm_submit.py`. Resource overrides can be added to the profile with Snakemake 7 `set-resources`/`set-threads` settings. Do not reduce Trim Galore's allocation below its helper-process needs.

Main results:

- `results/QC/fastqc/`: reports for both raw mates; `results/QC/multiqc_report.html`: aggregated QC.
- `results/align/`: transcriptome BAMs, STAR final logs, and chimeric junctions. Alignment parameters are retained; unused large genomic SAM output is suppressed. Transcriptome alignments retain STAR's RSEM-compatible filtering and are not coordinate-sorted.
- `results/rsem/`: genes/isoforms results plus genome/transcript BAMs from RSEM.
- `results/logs/` and `logs/slurm/`: tool and scheduler logs.

Merged reads, trimmed reads, and unmapped FASTQs are marked temporary and removed by Snakemake after their consumers finish. Each tool shell uses private temporary space under configured project `tmpdir`; the controller uses `work/tmp`. Normal exits clean private scratch. Slurm SIGKILL/node failure may leave scratch behind; remove only directories from jobs confirmed finished. Indexes and principal results are retained.

The original optional Kraken/Bracken include is omitted: neither module was listed and neither was part of the original default RNA-seq target. TRUST4 was only mentioned in an upstream comment. This adaptation does not add microbial or immune-repertoire analyses.

## Local verification

Validated with Python 3.10.9 and Snakemake 7.3.8: all 10 regression checks and the 16-job synthetic dry run passed. The launcher defaults to the h4h modules `python3/3.10.9` and `snakemake/7.3.8`. Site module execution still needs verification on h4h.

After loading the h4h runner modules (or in the local test environment), run:

```bash
python -m unittest discover -s tests -v
python tests/dry_run.py
bash -n scripts/run_h4h.sh
```

The dry run creates tiny two-sample/multi-lane fixtures and checks the complete job graph and shell formatting, without submitting Slurm jobs or executing scientific tools. Tests cover sample pairing, reference contig mismatch, resource limits, and Slurm completion/failure/accounting delays. Live h4h modules and full biological outputs require validation on the cluster.

The status helper treats empty accounting results as pending, never successful. If `sacct` is unavailable persistently, a completed job may remain pending in Snakemake; investigate scheduler accounting rather than treating an unknown job as successful.

References: [Snakemake 7 cluster options](https://snakemake.readthedocs.io/en/v7.3.8/executing/cli.html), [STAR manual](https://github.com/alexdobin/STAR/blob/master/doc/STARmanual.pdf), [RSEM documentation](https://github.com/deweylab/RSEM).
