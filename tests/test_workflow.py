"""Regression checks for sample pairing, reference mismatches and Slurm failures."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from workflow_utils import read_samples, check_reference, path_is_within
from slurm_status import status
from slurm_submit import command


class Inputs(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def sheet(self, text):
        path = self.root / 'samples.tsv'
        path.write_text(text)
        return path

    def test_path_guard_without_new_pathlib_api(self):
        with patch.object(Path, 'is_relative_to', None, create=True):
            self.assertTrue(path_is_within('/cluster/tools', '/cluster/tools'))
            self.assertTrue(path_is_within('/cluster/tools/data', '/cluster/tools'))
            self.assertFalse(path_is_within('/cluster/tools-other', '/cluster/tools'))
            self.assertFalse(path_is_within('/cluster/tools/../projects', '/cluster/tools'))
            target = self.root / 'protected'
            target.mkdir()
            alias = self.root / 'alias'
            alias.symlink_to(target, target_is_directory=True)
            self.assertTrue(path_is_within(alias / 'data', target))

    def test_multi_lane_order(self):
        data = read_samples(self.sheet('Sample\tFastq1\tFastq2\ns1\ta.fq.gz\tb.fq.gz\ns1\tc.fq.gz\td.fq.gz\n'))
        self.assertEqual([Path(p).name for p in data['s1']['r1']], ['a.fq.gz', 'c.fq.gz'])
        self.assertEqual([Path(p).name for p in data['s1']['r2']], ['b.fq.gz', 'd.fq.gz'])

    def test_duplicate_mate_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Reused FASTQ'):
            read_samples(self.sheet('Sample,Fastq1,Fastq2\ns1,a.fq.gz,a.fq.gz\n'))

    def test_missing_mate_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            read_samples(self.sheet('Sample,Fastq1,Fastq2\ns1,a.fq.gz,\n'))

    def test_sample_path_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsafe sample'):
            read_samples(self.sheet('Sample,Fastq1,Fastq2\n../bad,a.fq.gz,b.fq.gz\n'))

    def test_contig_mismatch_rejected(self):
        fasta, gtf = self.root / 'ref.fa', self.root / 'ref.gtf'
        fasta.write_text('>chr1\nACGTACGT\n')
        gtf.write_text('1\ttest\texon\t1\t4\t.\t+\t.\tgene_id "g"; transcript_id "t";\n')
        with self.assertRaisesRegex(ValueError, 'missing from FASTA'):
            check_reference(fasta, gtf)
        gtf.write_text(gtf.read_text().replace('1\ttest', 'chr1\ttest'))
        self.assertEqual(check_reference(fasta, gtf), (1, 1))


class Slurm(unittest.TestCase):
    def test_partition_and_per_task_cpus(self):
        props = {'rule': 'star', 'threads': 8,
                 'resources': {'time': 240, 'mem_mb': 48000, 'partition': 'himem'}}
        with tempfile.TemporaryDirectory() as tmp, patch('slurm_submit.Path.cwd', return_value=Path(tmp)):
            args = command(props, '/tmp/job.sh')
        self.assertIn('--cpus-per-task=8', args)
        self.assertIn('--ntasks=1', args)
        self.assertIn('--mem=48000M', args)
        self.assertIn('--partition=himem', args)
        props['resources']['partition'] = 'all'
        with self.assertRaisesRegex(ValueError, 'exceed'):
            command(props, '/tmp/job.sh')

    @patch('slurm_status.subprocess.run')
    def test_oom_overrides_successful_step(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '42|OUT_OF_MEMORY|\n42.batch|COMPLETED|\n', '')
        self.assertEqual(status('42'), 'failed')

    @patch('slurm_status.subprocess.run')
    def test_completed_job(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '42|COMPLETED|\n', '')
        self.assertEqual(status('42'), 'success')

    @patch('slurm_status.subprocess.run')
    def test_accounting_delay_is_not_success(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '', '')
        self.assertEqual(status('42'), 'running')

    @patch('slurm_status.subprocess.run')
    def test_queue_fallback(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 1, '', 'unavailable'),
                           subprocess.CompletedProcess([], 0, 'RUNNING\n', '')]
        self.assertEqual(status('42'), 'running')


if __name__ == '__main__':
    unittest.main()
