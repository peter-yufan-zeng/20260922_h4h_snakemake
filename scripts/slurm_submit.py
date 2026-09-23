#!/usr/bin/env python3
"""Submit one Snakemake 7 job with explicit h4h CPU/memory/time requests."""
import os
from pathlib import Path
import subprocess
import sys
from snakemake.utils import read_job_properties


def command(properties, jobscript):
    resources = properties['resources']
    threads = int(properties['threads'])
    memory, minutes = int(resources['mem_mb']), int(resources['time'])
    if min(threads, memory, minutes) < 1:
        raise ValueError('CPU, memory and time requests must be positive.')
    partition = resources['partition']
    # Limits from the supplied h4h guide; confirm current limits with sinfo.
    limits = {'all': (30720, 7200), 'himem': (61440, 10080),
              'veryhimem': (184320, 7200), 'long': (30720, 30240)}
    if partition in limits:
        max_mem, max_minutes = limits[partition]
        if memory > max_mem or minutes > max_minutes:
            raise ValueError(f'Resources exceed documented {partition} limits; select another partition.')
    logdir = Path('logs/slurm').resolve()
    logdir.mkdir(parents=True, exist_ok=True)
    name = properties.get('rule', properties.get('groupid', 'rnaseq'))
    args = ['sbatch', '--parsable', '--nodes=1', '--ntasks=1',
            f'--cpus-per-task={threads}', f'--mem={memory}M',
            f'--time={minutes}', f'--partition={partition}',
            f'--job-name=rnaseq_{name}', f'--output={logdir}/%x-%j.out']
    if os.environ.get('H4H_ACCOUNT'):
        args.append('--account=' + os.environ['H4H_ACCOUNT'])
    return args + [str(Path(jobscript).resolve())]


def main():
    jobscript = sys.argv[-1]
    result = subprocess.check_output(command(read_job_properties(jobscript), jobscript), text=True)
    jobid = result.strip().split(';')[0]
    if not jobid.isdigit():
        raise ValueError(f'Unexpected sbatch response: {result!r}')
    print(jobid)


if __name__ == '__main__':
    main()
