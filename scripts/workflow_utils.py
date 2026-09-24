"""Input validation shared by the workflow and preflight command."""
import csv
from pathlib import Path
import re


def path_is_within(path, parent):
    """Check containment without Path.is_relative_to (unavailable before Python 3.9)."""
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
    except ValueError:
        return False
    return True


def read_samples(filename):
    with open(filename, newline='') as handle:
        header = handle.readline()
        handle.seek(0)
        reader = csv.DictReader(handle, delimiter='\t' if '\t' in header else ',')
        if reader.fieldnames != ['Sample', 'Fastq1', 'Fastq2']:
            raise ValueError('Sample sheet must have columns Sample, Fastq1, Fastq2 (TSV or CSV).')
        samples, seen = {}, set()
        for line, row in enumerate(reader, 2):
            if None in row or any(not value or not value.strip() for value in row.values()):
                raise ValueError(f'Incomplete sample row {line}.')
            sample, r1, r2 = (row[key].strip() for key in reader.fieldnames)
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', sample):
                raise ValueError(f'Unsafe sample name at row {line}: {sample!r}')
            paths = [str(Path(p).expanduser().resolve()) for p in (r1, r2)]
            if paths[0] == paths[1] or any(p in seen for p in paths):
                raise ValueError(f'Reused FASTQ at row {line}; each mate/lane must be unique.')
            if any(not p.endswith(('.fq.gz', '.fastq.gz')) for p in paths):
                raise ValueError(f'Row {line}: paired FASTQs must be gzip-compressed .fq.gz/.fastq.gz.')
            seen.update(paths)
            lanes = samples.setdefault(sample, {'r1': [], 'r2': []})
            lanes['r1'].append(paths[0])
            lanes['r2'].append(paths[1])
    if not samples:
        raise ValueError('Sample sheet is empty.')
    return samples


def check_reference(fasta, gtf):
    """Check contig names and exon coordinates without requiring a writable FASTA index."""
    lengths, name = {}, None
    with open(fasta) as handle:
        for line in handle:
            if line.startswith('>'):
                name = line[1:].split()[0]
                if name in lengths:
                    raise ValueError(f'Duplicate FASTA contig: {name}')
                lengths[name] = 0
            elif name:
                lengths[name] += len(line.strip())
    if not lengths:
        raise ValueError('No FASTA sequences found.')
    exons = 0
    with open(gtf) as handle:
        for number, line in enumerate(handle, 1):
            if line.startswith('#') or not line.strip():
                continue
            fields = line.rstrip('\n').split('\t')
            if len(fields) != 9:
                raise ValueError(f'GTF line {number}: expected 9 tab-separated fields.')
            if fields[2] != 'exon':
                continue
            if fields[0] not in lengths:
                raise ValueError(f'GTF contig {fields[0]!r} missing from FASTA; check assembly/chr naming.')
            if not 1 <= int(fields[3]) <= int(fields[4]) <= lengths[fields[0]]:
                raise ValueError(f'GTF line {number}: exon outside FASTA contig.')
            for attr in ('gene_id', 'transcript_id'):
                if not re.search(r'(?:^|;)\s*' + attr + r'\s+"[^"]+"', fields[8]):
                    raise ValueError(f'GTF exon line {number} lacks {attr}.')
            exons += 1
    if not exons:
        raise ValueError('GTF contains no exons.')
    return len(lengths), exons
