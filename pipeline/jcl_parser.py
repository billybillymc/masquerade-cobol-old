"""
JCL parser — extracts job structure, steps, programs, and dataset references.
Builds a job flow graph showing execution order and data dependencies.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DDStatement:
    name: str
    dataset: str
    disposition: str
    line: int


@dataclass
class JobStep:
    name: str
    program: str
    line: int
    condition: Optional[str]
    dd_statements: list[DDStatement] = field(default_factory=list)

    @property
    def input_datasets(self) -> list[str]:
        return [dd.dataset for dd in self.dd_statements
                if dd.disposition.startswith("SHR") or "OLD" in dd.disposition]

    @property
    def output_datasets(self) -> list[str]:
        return [dd.dataset for dd in self.dd_statements
                if "NEW" in dd.disposition or "MOD" in dd.disposition]


@dataclass
class JclJob:
    name: str
    source_file: str
    description: str
    steps: list[JobStep] = field(default_factory=list)

    @property
    def programs(self) -> list[str]:
        return [s.program for s in self.steps if s.program not in _UTILITY_PROGRAMS]

    @property
    def all_programs(self) -> list[str]:
        return [s.program for s in self.steps]

    @property
    def all_datasets(self) -> set[str]:
        ds = set()
        for s in self.steps:
            for dd in s.dd_statements:
                if dd.dataset:
                    ds.add(dd.dataset)
        return ds


_UTILITY_PROGRAMS = {
    "SORT", "IDCAMS", "IEFBR14", "IEBGENER", "IEBCOPY", "DFSRRC00",
    "IKJEFT01", "IRXJCL", "DSNUTILB", "DSNUPROC", "DFHCSDUP",
}

_RE_JOB = re.compile(r'^//(\w+)\s+JOB\s', re.IGNORECASE)
_RE_EXEC = re.compile(r'^//(\w+)\s+EXEC\s+PGM=(\w+)', re.IGNORECASE)
_RE_EXEC_PROC = re.compile(r'^//(\w+)\s+EXEC\s+(\w+)', re.IGNORECASE)
_RE_DD = re.compile(r'^//(\w+)\s+DD\s', re.IGNORECASE)
_RE_DSN = re.compile(r'DSN=([A-Z0-9.&()+ -]+)', re.IGNORECASE)
_RE_DISP = re.compile(r'DISP=\(?([^)]*)\)?', re.IGNORECASE)
_RE_COND = re.compile(r'COND=\(([^)]+)\)', re.IGNORECASE)
_RE_COMMENT = re.compile(r'^/\*|^//\*')


_NOISE_WORDS = {
    "copyright", "license", "apache", "amazon", "all rights reserved",
    "licensed under", "you may not", "without warranties", "distributed on",
    "either express", "language governing", "http://", "https://",
    "basis,", "kind,", "limitations under",
}


def _extract_description(lines: list[str]) -> str:
    """Extract descriptive comments near the top of the JCL."""
    desc_lines = []
    past_license = False
    star_count = 0
    for line in lines[:40]:
        if line.startswith("//*"):
            text = line[3:].strip()
            if text.startswith("*") or text.startswith("=") or text.startswith("-"):
                star_count += 1
                if star_count >= 2:
                    past_license = True
                continue
            lower = text.lower()
            if any(w in lower for w in _NOISE_WORDS):
                continue
            if not text:
                continue
            if past_license:
                desc_lines.append(text)
        elif past_license and desc_lines:
            break
    return " ".join(desc_lines).strip()


def _resolve_continuation(lines: list[str]) -> list[str]:
    """Merge JCL continuation lines (lines starting with // followed by spaces)."""
    resolved = []
    for line in lines:
        if line.startswith("//") and not _RE_COMMENT.match(line):
            stripped = line[2:].lstrip()
            if resolved and not stripped[:1].isalpha() and not stripped.startswith("*"):
                if resolved[-1].rstrip().endswith(","):
                    resolved[-1] = resolved[-1].rstrip() + " " + stripped
                    continue
        resolved.append(line)
    return resolved


def parse_jcl_file(filepath: Path) -> Optional[JclJob]:
    """Parse a single JCL file into a JclJob."""
    raw = filepath.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    job_name = filepath.stem.upper()
    description = _extract_description(lines)

    job_m = None
    for line in lines[:5]:
        job_m = _RE_JOB.match(line)
        if job_m:
            job_name = job_m.group(1)
            break

    job = JclJob(
        name=job_name,
        source_file=str(filepath),
        description=description,
    )

    current_step: Optional[JobStep] = None

    for i, line in enumerate(lines):
        line_num = i + 1

        exec_m = _RE_EXEC.match(line)
        if exec_m:
            cond_m = _RE_COND.search(line)
            current_step = JobStep(
                name=exec_m.group(1),
                program=exec_m.group(2).upper(),
                line=line_num,
                condition=cond_m.group(1) if cond_m else None,
            )
            job.steps.append(current_step)
            continue

        if not exec_m:
            exec_proc = _RE_EXEC_PROC.match(line)
            if exec_proc and "EXEC" in line.upper() and "PGM=" not in line.upper():
                cond_m = _RE_COND.search(line)
                current_step = JobStep(
                    name=exec_proc.group(1),
                    program=exec_proc.group(2).upper(),
                    line=line_num,
                    condition=cond_m.group(1) if cond_m else None,
                )
                job.steps.append(current_step)
                continue

        dd_m = _RE_DD.match(line)
        if dd_m and current_step:
            dd_name = dd_m.group(1)
            full_line = line
            j = i + 1
            while j < len(lines) and lines[j].startswith("//") \
                    and not _RE_DD.match(lines[j]) \
                    and not _RE_EXEC.match(lines[j]) \
                    and not _RE_COMMENT.match(lines[j]):
                full_line += " " + lines[j][2:].strip()
                j += 1

            dsn_m = _RE_DSN.search(full_line)
            disp_m = _RE_DISP.search(full_line)

            if dsn_m:
                dataset = dsn_m.group(1).strip().rstrip(",").rstrip(")")
                disposition = disp_m.group(1).strip() if disp_m else "SHR"
                current_step.dd_statements.append(DDStatement(
                    name=dd_name,
                    dataset=dataset,
                    disposition=disposition,
                    line=line_num,
                ))

    return job if job.steps else None


class JclIndex:
    """Index of all JCL jobs in a codebase."""

    def __init__(self, codebase_dir: str):
        self.jobs: dict[str, JclJob] = {}
        self._dataset_producers: dict[str, list[str]] = defaultdict(list)
        self._dataset_consumers: dict[str, list[str]] = defaultdict(list)
        self._program_jobs: dict[str, list[str]] = defaultdict(list)

        for jcl_file in Path(codebase_dir).rglob("*.jcl"):
            try:
                job = parse_jcl_file(jcl_file)
                if job:
                    self.jobs[job.name] = job
                    self._index_job(job)
            except Exception:
                continue

        for jcl_file in Path(codebase_dir).rglob("*.JCL"):
            if jcl_file.stem.upper() not in self.jobs:
                try:
                    job = parse_jcl_file(jcl_file)
                    if job:
                        self.jobs[job.name] = job
                        self._index_job(job)
                except Exception:
                    continue

    def _index_job(self, job: JclJob):
        for step in job.steps:
            self._program_jobs[step.program].append(job.name)
            for ds in step.output_datasets:
                self._dataset_producers[ds].append(job.name)
            for ds in step.input_datasets:
                self._dataset_consumers[ds].append(job.name)

    def summary(self) -> dict:
        total_steps = sum(len(j.steps) for j in self.jobs.values())
        all_programs = set()
        cobol_programs = set()
        for j in self.jobs.values():
            for s in j.steps:
                all_programs.add(s.program)
                if s.program not in _UTILITY_PROGRAMS:
                    cobol_programs.add(s.program)

        all_datasets = set()
        for j in self.jobs.values():
            all_datasets |= j.all_datasets

        return {
            "total_jobs": len(self.jobs),
            "total_steps": total_steps,
            "unique_programs": len(all_programs),
            "cobol_programs": sorted(cobol_programs),
            "utility_programs": sorted(all_programs & _UTILITY_PROGRAMS),
            "total_datasets": len(all_datasets),
        }

    def job_detail(self, job_name: str) -> Optional[dict]:
        job = self.jobs.get(job_name.upper())
        if not job:
            return None
        return {
            "name": job.name,
            "source_file": job.source_file,
            "description": job.description,
            "steps": [
                {
                    "name": s.name,
                    "program": s.program,
                    "is_utility": s.program in _UTILITY_PROGRAMS,
                    "condition": s.condition,
                    "inputs": s.input_datasets,
                    "outputs": s.output_datasets,
                    "line": s.line,
                }
                for s in job.steps
            ],
        }

    def jobs_for_program(self, program: str) -> list[str]:
        return self._program_jobs.get(program.upper(), [])

    def dataset_flow(self) -> list[dict]:
        """Find datasets that connect jobs (produced by one, consumed by another)."""
        flows = []
        for ds, producers in self._dataset_producers.items():
            consumers = self._dataset_consumers.get(ds, [])
            if producers and consumers:
                for p in set(producers):
                    for c in set(consumers):
                        if p != c:
                            flows.append({
                                "dataset": ds,
                                "producer": p,
                                "consumer": c,
                            })
        return flows

    def execution_order(self) -> list[list[str]]:
        """Topological layers based on dataset dependencies between jobs.
        
        Returns list of layers; jobs in the same layer can run in parallel.
        """
        flows = self.dataset_flow()
        deps: dict[str, set[str]] = defaultdict(set)
        all_jobs = set(self.jobs.keys())

        for f in flows:
            deps[f["consumer"]].add(f["producer"])

        placed = set()
        layers = []

        while placed != all_jobs:
            layer = []
            for j in all_jobs - placed:
                unmet = deps.get(j, set()) - placed
                if not unmet:
                    layer.append(j)
            if not layer:
                layer = sorted(all_jobs - placed)
            layers.append(sorted(layer))
            placed |= set(layer)

        return layers
