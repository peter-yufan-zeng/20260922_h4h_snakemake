#!/usr/bin/env python3
"""Build the complete DAG with tiny paired multi-lane fixtures; no bioinformatics tools run."""
import gzip
import os
from pathlib import Path
import subprocess
import tempfile
import yaml

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='h4h-dryrun-') as directory:
    root = Path(directory)
    os.environ['XDG_CACHE_HOME'] = str(root / 'cache')
    cfg = yaml.safe_load((ROOT / 'config/h4h.yaml').read_text())
    rows = ['Sample\tFastq1\tFastq2']
    for sample, lanes in [('mouse01', 2), ('mouse02', 1)]:
        for lane in range(lanes):
            mates = []
            for mate in (1, 2):
                path = root / f'{sample}_L{lane}_R{mate}.fq.gz'
                with gzip.open(path, 'wt') as handle:
                    handle.write('@read\nACGT\n+\nIIII\n')
                mates.append(str(path))
            rows.append('\t'.join([sample] + mates))
    sheet = root / 'samples.tsv'
    sheet.write_text('\n'.join(rows) + '\n')
    fasta, gtf = root / 'mouse.fa', root / 'mouse.gtf'
    fasta.write_text('>chr1\nACGTACGT\n')
    gtf.write_text('chr1\ttest\texon\t1\t4\t.\t+\t.\tgene_id "g"; transcript_id "t";\n')
    cfg.update(input=str(sheet), outdir=str(root / 'results'), tmpdir=str(root / 'tmp'))
    cfg['reference'].update(fasta=str(fasta), gtf=str(gtf), index_dir=str(root / 'index'))
    config = root / 'config.yaml'
    config.write_text(yaml.safe_dump(cfg))
    subprocess.run(['python', 'scripts/preflight.py', '--config', str(config), '--skip-modules'], cwd=ROOT, check=True)
    subprocess.run(['snakemake', '-s', 'run_rnaseq_mouse.snk', '--profile', 'profiles/h4h',
                    '--configfile', str(config), '--cores', '8', '--dry-run', '--printshellcmds'], cwd=ROOT, check=True)
