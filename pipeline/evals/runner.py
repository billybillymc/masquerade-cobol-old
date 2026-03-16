"""
Evaluation runner for the COBOL RAG pipeline.

Usage:
    python -m evals.runner                          # run all test cases
    python -m evals.runner --codebase carddemo      # run one codebase
    python -m evals.runner --id cd-signon           # run one test case
    python -m evals.runner --dry-run                # show test cases without running
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag_config import register_codebase, CODEBASES


EVALS_DIR = Path(__file__).resolve().parent
TEST_CASES_FILE = EVALS_DIR / "test_cases.json"
RESULTS_DIR = EVALS_DIR / "results"

_project_root = Path(__file__).resolve().parent.parent.parent
_test_codebases = _project_root / "test-codebases"


@dataclass
class EvalScore:
    """Scoring result for one test case."""
    test_id: str
    question: str
    codebase: str
    difficulty: str

    # Retrieval metrics
    program_recall: float = 0.0
    keyword_hit_rate: float = 0.0
    source_relevance: float = 0.0

    # Answer quality (heuristic)
    answer_length: int = 0
    has_evidence: bool = False
    mentions_uncertainty: bool = False

    # Performance
    latency_ms: float = 0.0

    # Composite
    composite_score: float = 0.0

    details: dict = field(default_factory=dict)
    error: Optional[str] = None


def _load_test_cases() -> list[dict]:
    with open(TEST_CASES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _register_codebases():
    known = {
        "carddemo": str(_test_codebases / "carddemo"),
        "taxe-fonciere": str(_test_codebases / "taxe-fonciere"),
    }
    for name, d in known.items():
        if Path(d).is_dir():
            register_codebase(name, d)


def _score_retrieval(result, test_case: dict) -> dict:
    """Score retrieval quality against expected programs and keywords."""
    expected_programs = [p.upper() for p in test_case.get("expected_programs", [])]
    expected_keywords = [k.lower() for k in test_case.get("expected_keywords", [])]

    retrieved_programs = set()
    for src in result.sources:
        if src.chunk.program_name:
            retrieved_programs.add(src.chunk.program_name.upper())

    # Program recall: what fraction of expected programs were retrieved
    if expected_programs:
        found = sum(1 for p in expected_programs if p in retrieved_programs)
        program_recall = found / len(expected_programs)
    else:
        program_recall = 1.0  # no expectation = pass

    # Keyword hit rate: what fraction of expected keywords appear in the answer
    answer_lower = result.answer.lower()
    if expected_keywords:
        hits = sum(1 for k in expected_keywords if k in answer_lower)
        keyword_hit_rate = hits / len(expected_keywords)
    else:
        keyword_hit_rate = 1.0

    # Source relevance: average score of top sources
    top_scores = [s.score for s in result.sources[:5]]
    source_relevance = sum(top_scores) / len(top_scores) if top_scores else 0.0

    return {
        "program_recall": program_recall,
        "keyword_hit_rate": keyword_hit_rate,
        "source_relevance": source_relevance,
        "retrieved_programs": sorted(retrieved_programs),
        "expected_programs": expected_programs,
        "keyword_hits": [k for k in expected_keywords if k in answer_lower],
        "keyword_misses": [k for k in expected_keywords if k not in answer_lower],
    }


def _score_answer_quality(result) -> dict:
    """Heuristic answer quality checks."""
    answer = result.answer

    has_evidence = any(
        marker in answer.lower()
        for marker in ["program", "paragraph", "copybook", "section", "file", "line"]
    )

    mentions_uncertainty = any(
        marker in answer.lower()
        for marker in [
            "unclear", "uncertain", "not found", "insufficient",
            "may", "might", "appears to", "seems", "likely",
        ]
    )

    return {
        "answer_length": len(answer),
        "has_evidence": has_evidence,
        "mentions_uncertainty": mentions_uncertainty,
    }


def _compute_composite(retrieval: dict, quality: dict, latency_ms: float) -> float:
    """Weighted composite score (0-100)."""
    retrieval_score = (
        retrieval["program_recall"] * 0.40
        + retrieval["keyword_hit_rate"] * 0.30
        + min(retrieval["source_relevance"], 1.0) * 0.10
    ) * 100

    quality_score = 0.0
    if quality["has_evidence"]:
        quality_score += 10
    if quality["answer_length"] > 100:
        quality_score += 5
    if quality["answer_length"] > 300:
        quality_score += 5

    return min(100, retrieval_score + quality_score)


def run_single(test_case: dict) -> EvalScore:
    """Run a single evaluation test case."""
    from synthesis.chain import query

    score = EvalScore(
        test_id=test_case["id"],
        question=test_case["question"],
        codebase=test_case["codebase"],
        difficulty=test_case.get("difficulty", "medium"),
    )

    try:
        result = query(test_case["question"], codebase_filter=test_case["codebase"])

        retrieval = _score_retrieval(result, test_case)
        quality = _score_answer_quality(result)

        score.program_recall = retrieval["program_recall"]
        score.keyword_hit_rate = retrieval["keyword_hit_rate"]
        score.source_relevance = retrieval["source_relevance"]
        score.answer_length = quality["answer_length"]
        score.has_evidence = quality["has_evidence"]
        score.mentions_uncertainty = quality["mentions_uncertainty"]
        score.latency_ms = result.latency_ms
        score.composite_score = _compute_composite(retrieval, quality, result.latency_ms)
        score.details = {
            "retrieval": retrieval,
            "quality": quality,
            "answer_preview": result.answer[:300],
        }

    except Exception as e:
        score.error = str(e)
        score.composite_score = 0.0

    return score


def run_all(
    codebase_filter: str = None,
    test_id: str = None,
) -> list[EvalScore]:
    """Run all (or filtered) test cases and return scores."""
    cases = _load_test_cases()

    if codebase_filter:
        cases = [c for c in cases if c["codebase"] == codebase_filter]
    if test_id:
        cases = [c for c in cases if c["id"] == test_id]

    if not cases:
        print("No matching test cases found.")
        return []

    print(f"\n  Running {len(cases)} eval cases...\n")

    scores: list[EvalScore] = []
    for i, case in enumerate(cases, 1):
        if i > 1:
            time.sleep(7)  # respect Cohere trial rate limit (10/min)
        print(f"  [{i}/{len(cases)}] {case['id']}: {case['question'][:60]}...", end="", flush=True)
        t0 = time.perf_counter()
        score = run_single(case)
        elapsed = (time.perf_counter() - t0) * 1000

        if score.error:
            status = f"\033[38;5;196mERROR\033[0m"
        elif score.composite_score >= 70:
            status = f"\033[38;5;40m{score.composite_score:.0f}\033[0m"
        elif score.composite_score >= 45:
            status = f"\033[38;5;214m{score.composite_score:.0f}\033[0m"
        else:
            status = f"\033[38;5;196m{score.composite_score:.0f}\033[0m"

        print(f"  {status}  ({elapsed:.0f}ms)")
        scores.append(score)

    return scores


def print_report(scores: list[EvalScore]):
    """Print a summary report of eval results."""
    if not scores:
        return

    print(f"\n  \033[38;5;214m{'=' * 65}\033[0m")
    print(f"  \033[38;5;214m  EVALUATION REPORT\033[0m")
    print(f"  \033[38;5;214m{'=' * 65}\033[0m\n")

    print(f"  {'Test ID':<25s} {'Score':>5s}  {'Prog':>5s}  {'KW':>5s}  {'Lat':>6s}  {'Diff':<6s}")
    print(f"  {'-'*25} {'-'*5}  {'-'*5}  {'-'*5}  {'-'*6}  {'-'*6}")

    for s in scores:
        if s.error:
            print(f"  {s.test_id:<25s}  \033[38;5;196mERROR: {s.error[:40]}\033[0m")
            continue

        cs = s.composite_score
        if cs >= 70:
            color = "\033[38;5;40m"
        elif cs >= 45:
            color = "\033[38;5;214m"
        else:
            color = "\033[38;5;196m"

        print(
            f"  {s.test_id:<25s}"
            f" {color}{cs:>5.0f}\033[0m"
            f"  {s.program_recall * 100:>4.0f}%"
            f"  {s.keyword_hit_rate * 100:>4.0f}%"
            f"  {s.latency_ms:>5.0f}ms"
            f"  {s.difficulty:<6s}"
        )

    # Summary stats
    valid = [s for s in scores if not s.error]
    if valid:
        avg_score = sum(s.composite_score for s in valid) / len(valid)
        avg_latency = sum(s.latency_ms for s in valid) / len(valid)
        avg_recall = sum(s.program_recall for s in valid) / len(valid)
        avg_kw = sum(s.keyword_hit_rate for s in valid) / len(valid)
        passing = sum(1 for s in valid if s.composite_score >= 60)
        errors = sum(1 for s in scores if s.error)

        print(f"\n  \033[38;5;245m{'-' * 65}\033[0m")
        print(f"  Avg score:    \033[1m{avg_score:.1f}/100\033[0m")
        print(f"  Avg recall:   {avg_recall * 100:.0f}%")
        print(f"  Avg keywords: {avg_kw * 100:.0f}%")
        print(f"  Avg latency:  {avg_latency:.0f}ms")
        print(f"  Pass rate:    {passing}/{len(valid)} ({passing/len(valid)*100:.0f}%)")
        if errors:
            print(f"  \033[38;5;196mErrors: {errors}\033[0m")

    print(f"\n  \033[38;5;214m{'=' * 65}\033[0m\n")


def save_results(scores: list[EvalScore]):
    """Save eval results to JSON file."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    outfile = RESULTS_DIR / f"eval-{timestamp}.json"
    data = [asdict(s) for s in scores]
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Results saved to {outfile}")


def main():
    parser = argparse.ArgumentParser(description="Run COBOL RAG evaluation suite")
    parser.add_argument("--codebase", help="Filter to specific codebase")
    parser.add_argument("--id", help="Run a single test case by ID")
    parser.add_argument("--dry-run", action="store_true", help="Show test cases without running")
    parser.add_argument("--no-save", action="store_true", help="Don't save results to disk")
    args = parser.parse_args()

    _register_codebases()

    if args.dry_run:
        cases = _load_test_cases()
        if args.codebase:
            cases = [c for c in cases if c["codebase"] == args.codebase]
        print(f"\n  {len(cases)} test cases:\n")
        for c in cases:
            print(f"  [{c['id']}] ({c['codebase']}) {c['question']}")
            if c.get("expected_programs"):
                print(f"    expected: {', '.join(c['expected_programs'])}")
            print(f"    keywords: {', '.join(c['expected_keywords'])}")
            print(f"    difficulty: {c.get('difficulty', 'medium')}")
            print()
        return

    scores = run_all(codebase_filter=args.codebase, test_id=args.id)
    print_report(scores)

    if not args.no_save and scores:
        save_results(scores)


if __name__ == "__main__":
    main()
