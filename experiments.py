"""Reproducible experiments for the complete Griductive deduction loop.

Each official puzzle is loaded through the production puzzle loader and then
solved from its initial public knowledge base by repeatedly calling
``GameEngine.auto_solve_step``.  The benchmark therefore measures the same
progressive reveal protocol used by the GUI; it never activates every clue at
the start.

Usage
-----
    python experiments.py
    python experiments.py --runs 10 --timeout 5

Output
------
    output/experiments/results.csv
    output/experiments/results.md
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.agent import AgentMetrics, DeductiveAgent  # noqa: E402
from core.encoder import CNFEncoder  # noqa: E402
from core.engine import GameEngine  # noqa: E402
from core.puzzle import PuzzleDefinition, load_puzzle  # noqa: E402


@dataclass
class BenchmarkResult:
    """One report row, including unsuccessful and timed-out runs."""

    puzzle_file: str
    name: str
    grid_size: str = "-"
    status: str = "FAILED"
    runs_requested: int = 0
    runs_completed: int = 0
    num_primary_vars: int = 0
    num_aux_vars: int = 0
    initial_clauses: int = 0
    full_clauses: int = 0
    sat_calls: int = 0
    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    deduction_steps: int = 0
    forced_count: int = 0
    unknown_count: int = 0
    is_consistent: Optional[bool] = None
    is_unique: Optional[bool] = None
    mean_runtime_ms: float = 0.0
    error: str = ""


def _build_measurement_snapshots(puzzle: PuzzleDefinition):
    """Build the initial and complete public-KB snapshots for clause counts."""
    all_ids = list(puzzle.cell_ids)
    all_clues = list(puzzle.clues)
    initial_known = {
        cell_id: puzzle.hidden_solution[cell_id]
        for cell_id in puzzle.initial_revealed
    }
    initial_clue_ids = [
        puzzle.cell_map[cell_id].clue.id
        for cell_id in puzzle.initial_revealed
    ]
    encoder = CNFEncoder(character_ids=all_ids, grid_size=puzzle.size)
    initial_snapshot = encoder.build_snapshot(
        all_cell_ids=all_ids,
        clues=all_clues,
        active_clue_ids=initial_clue_ids,
        known_statuses=initial_known,
    )
    full_snapshot = encoder.build_snapshot(
        all_cell_ids=all_ids,
        clues=all_clues,
        active_clue_ids=[clue.id for clue in all_clues],
        known_statuses=initial_known,
    )
    return initial_snapshot, full_snapshot


def _base_result(
    puzzle: PuzzleDefinition,
    puzzle_file: str,
    runs: int,
) -> BenchmarkResult:
    initial_snapshot, full_snapshot = _build_measurement_snapshots(puzzle)
    result = BenchmarkResult(
        puzzle_file=puzzle_file,
        name=puzzle.name,
        grid_size=f"{puzzle.size}x{puzzle.size}",
        runs_requested=runs,
        num_primary_vars=len(full_snapshot.cell_to_var),
        num_aux_vars=full_snapshot.aux_var_count,
        initial_clauses=initial_snapshot.clause_count,
        full_clauses=full_snapshot.clause_count,
    )

    # Uniqueness is a property of the complete clue set plus the initially
    # public statuses.  Its SAT calls are intentionally not mixed into the
    # progressive deduction metrics below.
    agent = DeductiveAgent()
    consistency_metrics = AgentMetrics()
    result.is_consistent = agent.check_consistency(
        full_snapshot, consistency_metrics
    )
    if result.is_consistent:
        result.is_unique, _ = agent.check_uniqueness(full_snapshot)
    else:
        result.is_unique = False
    return result


def run_benchmark(
    puzzle: PuzzleDefinition,
    *,
    puzzle_file: str = "",
    runs: int = 10,
    timeout_seconds: float = 5.0,
) -> BenchmarkResult:
    """Run the production deduction loop repeatedly for one puzzle.

    ``timeout_seconds`` applies to each repetition.  The DPLL implementation
    is synchronous, so the deadline is checked before and after every complete
    deduction step.
    """
    if isinstance(runs, bool) or not isinstance(runs, int) or runs <= 0:
        raise ValueError("runs must be a positive integer.")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive.")

    result = _base_result(puzzle, puzzle_file, runs)
    runtimes: list[float] = []
    reference_metrics: Optional[tuple[int, int, int, int, int]] = None

    for run_index in range(1, runs + 1):
        engine = GameEngine(puzzle)
        run_started = time.perf_counter()

        try:
            while engine.phase == "ACTIVE":
                elapsed = time.perf_counter() - run_started
                if elapsed >= timeout_seconds:
                    result.status = "TIMEOUT"
                    result.error = (
                        f"Run {run_index} exceeded {timeout_seconds:.3f}s "
                        "before the next deduction step."
                    )
                    return result

                action = engine.auto_solve_step()

                elapsed = time.perf_counter() - run_started
                if elapsed >= timeout_seconds:
                    result.status = "TIMEOUT"
                    result.error = (
                        f"Run {run_index} exceeded {timeout_seconds:.3f}s "
                        "after a deduction step."
                    )
                    return result
                if action.code not in {"ACCEPTED", "SOLVED"}:
                    break
        except Exception as error:  # Preserve the failed row in the report.
            result.status = "FAILED"
            result.error = f"Run {run_index}: {type(error).__name__}: {error}"
            return result

        metrics = engine.metrics
        current_metrics = (
            metrics.sat_calls,
            metrics.total_decisions,
            metrics.total_propagations,
            metrics.total_backtracks,
            engine.step,
        )
        if engine.phase != "SOLVED":
            result.status = engine.phase
            result.sat_calls = metrics.sat_calls
            result.decisions = metrics.total_decisions
            result.propagations = metrics.total_propagations
            result.backtracks = metrics.total_backtracks
            result.deduction_steps = engine.step
            result.forced_count = engine.step
            result.unknown_count = (
                len(puzzle.cells)
                - len(puzzle.initial_revealed)
                - engine.step
            )
            result.error = (
                f"Run {run_index} ended in phase {engine.phase}; "
                "the public KB could not complete the puzzle."
            )
            return result

        if reference_metrics is None:
            reference_metrics = current_metrics
        elif current_metrics != reference_metrics:
            result.status = "FAILED"
            result.error = (
                "Deterministic metrics changed between repeated runs: "
                f"expected {reference_metrics}, got {current_metrics}."
            )
            return result

        result.runs_completed += 1
        runtimes.append(metrics.total_runtime_ms)

    assert reference_metrics is not None
    (
        result.sat_calls,
        result.decisions,
        result.propagations,
        result.backtracks,
        result.deduction_steps,
    ) = reference_metrics
    result.forced_count = result.deduction_steps
    result.unknown_count = 0
    result.mean_runtime_ms = mean(runtimes)
    result.status = "OK"
    return result


def benchmark_file(
    path: Path,
    *,
    runs: int = 10,
    timeout_seconds: float = 5.0,
) -> BenchmarkResult:
    """Load and benchmark one file without dropping load failures."""
    try:
        puzzle = load_puzzle(path)
        return run_benchmark(
            puzzle,
            puzzle_file=path.name,
            runs=runs,
            timeout_seconds=timeout_seconds,
        )
    except Exception as error:
        return BenchmarkResult(
            puzzle_file=path.name,
            name=path.stem,
            status="FAILED",
            runs_requested=runs,
            error=f"{type(error).__name__}: {error}",
        )


CSV_HEADERS = [
    "Puzzle File",
    "Name",
    "Grid",
    "Status",
    "Runs",
    "Completed Runs",
    "Primary Vars",
    "Aux Vars",
    "Initial Clauses",
    "Full Clauses",
    "SAT Calls",
    "Decisions",
    "Propagations",
    "Backtracks",
    "Deduction Steps",
    "Forced",
    "Unknown",
    "Consistent",
    "Unique",
    "Mean Runtime (ms)",
    "Error",
]


def _display_optional(value: Optional[bool]) -> str:
    return "N/A" if value is None else str(value)


def result_to_row(result: BenchmarkResult) -> list[object]:
    return [
        result.puzzle_file,
        result.name,
        result.grid_size,
        result.status,
        result.runs_requested,
        result.runs_completed,
        result.num_primary_vars,
        result.num_aux_vars,
        result.initial_clauses,
        result.full_clauses,
        result.sat_calls,
        result.decisions,
        result.propagations,
        result.backtracks,
        result.deduction_steps,
        result.forced_count,
        result.unknown_count,
        _display_optional(result.is_consistent),
        _display_optional(result.is_unique),
        f"{result.mean_runtime_ms:.3f}",
        result.error,
    ]


def export_csv(results: Iterable[BenchmarkResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(CSV_HEADERS)
        for result in results:
            writer.writerow(result_to_row(result))


def export_markdown(
    results: Iterable[BenchmarkResult],
    path: Path,
    *,
    timeout_seconds: float,
) -> None:
    result_list = list(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("# Experiment Results\n\n")
        handle.write(
            "Generated by `experiments.py`. Each successful row runs the "
            "production no-guess deduction loop from the initial public KB. "
            "SAT metrics describe one deterministic run; runtime is the mean "
            "cumulative DPLL runtime across the completed repetitions. "
            f"Per-run timeout: {timeout_seconds:.3f} seconds.\n\n"
        )

        headers = CSV_HEADERS[:-1]
        handle.write("| " + " | ".join(headers) + " |\n")
        handle.write("| " + " | ".join("---" for _ in headers) + " |\n")
        for result in result_list:
            row = result_to_row(result)[:-1]
            handle.write("| " + " | ".join(map(str, row)) + " |\n")

        handle.write("\n## Failures and timeouts\n\n")
        unsuccessful = [result for result in result_list if result.status != "OK"]
        if not unsuccessful:
            handle.write("No failures or timeouts were observed.\n")
        else:
            for result in unsuccessful:
                handle.write(
                    f"- **{result.puzzle_file} — {result.status}:** "
                    f"{result.error or 'No detail provided.'}\n"
                )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark the complete Griductive deduction loop."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=10,
        help="number of repetitions per puzzle (default: 10)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="timeout in seconds for each repetition (default: 5)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.runs <= 0:
        raise SystemExit("--runs must be a positive integer.")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive.")

    puzzle_files = sorted((PROJECT_ROOT / "puzzles").glob("level_*.json"))
    if not puzzle_files:
        raise SystemExit("No official level_*.json puzzle files were found.")

    print("Griductive progressive deduction experiments")
    print(f"Runs per puzzle: {args.runs}; timeout: {args.timeout:.3f}s")
    results: list[BenchmarkResult] = []
    for path in puzzle_files:
        result = benchmark_file(
            path,
            runs=args.runs,
            timeout_seconds=args.timeout,
        )
        results.append(result)
        print(
            f"[{result.status}] {path.name}: steps={result.deduction_steps}, "
            f"SAT calls={result.sat_calls}, "
            f"runtime={result.mean_runtime_ms:.3f}ms"
        )
        if result.error:
            print(f"    {result.error}")

    output_dir = PROJECT_ROOT / "output" / "experiments"
    export_csv(results, output_dir / "results.csv")
    export_markdown(
        results,
        output_dir / "results.md",
        timeout_seconds=args.timeout,
    )

    failed = sum(result.status != "OK" for result in results)
    print(f"Completed {len(results)} puzzle rows; unsuccessful rows: {failed}.")


if __name__ == "__main__":
    main()
