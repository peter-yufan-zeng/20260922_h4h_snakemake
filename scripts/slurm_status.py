#!/usr/bin/env python3
"""Check the allocation (not its .batch/.extern steps); allow accounting delays."""
import subprocess
import sys

ACTIVE = {'PENDING', 'RUNNING', 'SUSPENDED', 'COMPLETING', 'CONFIGURING',
          'RESIZING', 'REQUEUED', 'REQUEUE_FED', 'REQUEUE_HOLD', 'SIGNALING', 'STAGE_OUT'}


def classify(state):
    state = state.split()[0].rstrip('+')
    return 'success' if state == 'COMPLETED' else 'running' if state in ACTIVE else 'failed'


def status(jobid):
    accounting = subprocess.run(
        ['sacct', '-n', '-P', '-j', jobid, '--format=JobIDRaw,State'],
        capture_output=True, text=True)
    if accounting.returncode == 0:
        for line in accounting.stdout.splitlines():
            fields = line.split('|')
            if len(fields) >= 2 and fields[0].strip() == jobid and fields[1].strip():
                return classify(fields[1].strip())
    queue = subprocess.run(['squeue', '-h', '-j', jobid, '-o', '%T'], capture_output=True, text=True)
    if queue.returncode == 0 and queue.stdout.strip():
        return classify(queue.stdout.strip().splitlines()[0])
    # Neither an empty accounting result nor a temporary scheduler error means success.
    # If accounting never becomes available, operator intervention is required.
    print(f'Job {jobid}: awaiting Slurm accounting state.', file=sys.stderr)
    return 'running'


if __name__ == '__main__':
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit('Expected one numeric Slurm job ID')
    print(status(sys.argv[1]))
