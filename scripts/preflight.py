#!/usr/bin/env python3
"""Run on an h4h compute node before submitting the RNA-seq jobs."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import yaml
from workflow_utils import read_samples, check_reference, path_is_within


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config/h4h.yaml')
    parser.add_argument('--skip-modules', action='store_true', help='For local input validation only')
    args = parser.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())
    samples = read_samples(cfg['input'])
    for lanes in samples.values():
        for paths in lanes.values():
            for path in paths:
                with open(path, 'rb') as handle:
                    if handle.read(2) != b'\x1f\x8b':
                        raise ValueError(f'Not a gzip FASTQ: {path}')
    contigs, exons = check_reference(cfg['reference']['fasta'], cfg['reference']['gtf'])
    if cfg['strandedness'] not in ('none', 'forward', 'reverse'):
        raise ValueError('Invalid strandedness')
    if int(cfg['reference']['sjdb_overhang']) < 1:
        raise ValueError('sjdb_overhang must be positive')
    for directory in (cfg['outdir'], cfg['tmpdir'], cfg['reference']['index_dir']):
        path = Path(directory).resolve()
        if path_is_within(path, '/cluster/tools'):
            raise ValueError('Never write outputs or indexes into /cluster/tools')
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
    print(f'Validated {len(samples)} samples, {contigs} FASTA contigs, {exons} GTF exons.', flush=True)
    print('Contig/coordinate checks cannot prove annotation provenance: confirm both files are mm10.', flush=True)
    if not args.skip_modules:
        probes = {
            'fastqc': 'fastqc --version',
            'trim': 'cutadapt --version; trim_galore --version',
            'star': 'STAR --version',
            'rsem': 'command -v rsem-prepare-reference; rsem-calculate-expression --version; samtools --version',
            'multiqc': 'multiqc --version',
        }
        init = shlex.quote(cfg['modules_init'])
        for key, probe in probes.items():
            names = cfg['modules'][key]
            if not isinstance(names, list) or not names:
                raise ValueError(f'modules.{key} must be a non-empty list')
            load = ' '.join(shlex.quote(name) for name in names)
            code = (f'set -euo pipefail; if ! type module >/dev/null 2>&1; then source {init}; fi; '
                    f'module purge; module load {load}; module list; {probe}')
            subprocess.run(['/bin/bash', '-c', code], check=True,
                           env={**os.environ, 'TMPDIR': str(Path(cfg['tmpdir']).resolve()),
                                'TMP': str(Path(cfg['tmpdir']).resolve()),
                                'TEMP': str(Path(cfg['tmpdir']).resolve())})
    print('Preflight passed.')


if __name__ == '__main__':
    main()
