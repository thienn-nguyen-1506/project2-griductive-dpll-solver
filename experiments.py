"""Benchmark experiments for DPLL SAT Solver and Deductive Agent.

This script:
* Loads real puzzle JSON files from `puzzles/` and encodes them via `CNFEncoder`.
* Falls back to synthetic benchmarks if JSON files are missing or lack clues.
* Runs DeductiveAgent evaluation (SAT calls, propagations, backtracks, runtime).
* Exports results to CSV and Markdown for the report.

Usage
-----
    python experiments.py

Output
------
    output/experiments/results.csv
    output/experiments/results.md
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# Ensure project root is on sys.path so core package is importable.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.agent import (  # noqa: E402
    DeductiveAgent,
    KnowledgeBaseSnapshot,
)
from core.encoder import CNFEncoder, Clue  # noqa: E402


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    """One row in the experiment results table."""

    name: str
    grid_size: str                      # e.g. "3x3"
    num_primary_vars: int = 0
    num_aux_vars: int = 0
    num_clauses: int = 0
    sat_calls: int = 0
    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    deduction_steps: int = 0
    forced_count: int = 0
    unknown_count: int = 0
    is_consistent: bool = True
    is_unique: bool = True
    total_runtime_ms: float = 0.0


# ---------------------------------------------------------------------------
# JSON Loader via CNFEncoder
# ---------------------------------------------------------------------------

def _load_puzzle_from_json(json_path: Path) -> Tuple[str, KnowledgeBaseSnapshot, str]:
    """Load a puzzle JSON file and encode it into CNF using CNFEncoder."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Trích xuất kích thước lưới (Đọc 'grid' hoặc 'size' từ root)
    grid_data = data.get("grid", {})
    if isinstance(grid_data, dict) and ("rows" in grid_data or "cols" in grid_data):
        rows = grid_data.get("rows", 3)
        cols = grid_data.get("cols", 3)
    else:
        size = data.get("size", 3)
        rows = cols = size

    grid_size = f"{rows}x{cols}"

    # 2. Trích xuất danh sách ô (cell_ids)
    if isinstance(grid_data, dict) and "cells" in grid_data:
        cell_ids = [c["id"] for c in grid_data["cells"] if isinstance(c, dict) and "id" in c]
    else:
        cell_ids = [f"{chr(65 + c)}{r + 1}" for r in range(rows) for c in range(cols)]

    # 3. Trích xuất manh mối (clues)
    raw_clues = (
        data.get("clues")
        or data.get("initial_clues")
        or (grid_data.get("clues") if isinstance(grid_data, dict) else [])
        or []
    )

    # Nếu không có clue (file mock của GUI), báo lỗi để chuyển sang synthetic benchmark
    if not raw_clues:
        raise ValueError(f"File '{json_path.name}' không chứa clues (file GUI mock).")

    clues: List[Clue] = []
    for idx, c in enumerate(raw_clues):
        if not isinstance(c, dict):
            continue
        clues.append(
            Clue(
                id=c.get("id", f"clue_{idx}"),
                type=c.get("type"),
                target=c.get("target"),
                targets=c.get("targets", []),
                value=c.get("value"),
                count=c.get("count"),
            )
        )

    # 4. Mã hóa bằng CNFEncoder
    encoder = CNFEncoder(character_ids=cell_ids)
    snapshot = encoder.build_snapshot(
        all_cell_ids=cell_ids,
        clues=clues,
        active_clue_ids=[c.id for c in clues],
        known_statuses={},
    )

    name = f"Puzzle {json_path.stem}"
    return name, snapshot, grid_size


# ---------------------------------------------------------------------------
# Fallback Synthetic Generators
# ---------------------------------------------------------------------------

def _generate_3x3_synthetic() -> Tuple[str, KnowledgeBaseSnapshot, str]:
    cell_ids = ["A1", "B1", "C1", "A2", "B2", "C2", "A3", "B3", "C3"]
    cell_to_var = {cid: i + 1 for i, cid in enumerate(cell_ids)}

    clauses = [
        [1], [-2], [-3], [-5, 9], [5, -9],
        [-4, -5], [4, 5], [2, 5, 8], [-7, -8],
        [-7, -9], [-8, -9], [-6]
    ]

    snap = KnowledgeBaseSnapshot(
        clauses=clauses,
        primary_vars={f"C_{cid}": var for cid, var in cell_to_var.items()},
        unresolved_cell_ids=list(cell_ids),
        cell_to_var=cell_to_var,
        active_clue_ids=["clue1", "clue2", "clue3"],
        known_statuses={},
        aux_var_count=0,
    )
    return "Synthetic 3x3", snap, "3x3"


def _generate_4x4_synthetic() -> Tuple[str, KnowledgeBaseSnapshot, str]:
    cell_ids = [f"{c}{r}" for r in range(1, 5) for c in "ABCD"]
    cell_to_var = {cid: i + 1 for i, cid in enumerate(cell_ids)}

    clauses = [
        [1], [-2], [4], [-5], [6], [-7], [-8], [-9], [-10],
        [11], [-12], [13], [-14], [-15], [16], [-3], [-13, 16],
        [13, -16], [-2, -6], [2, 6], [3, 7, 11, 15]
    ]

    snap = KnowledgeBaseSnapshot(
        clauses=clauses,
        primary_vars={f"C_{cid}": var for cid, var in cell_to_var.items()},
        unresolved_cell_ids=list(cell_ids),
        cell_to_var=cell_to_var,
        active_clue_ids=["clue1", "clue2"],
        known_statuses={},
        aux_var_count=0,
    )
    return "Synthetic 4x4", snap, "4x4"


def _generate_5x5_synthetic() -> Tuple[str, KnowledgeBaseSnapshot, str]:
    cell_ids = [f"{c}{r}" for r in range(1, 6) for c in "ABCDE"]
    cell_to_var = {cid: i + 1 for i, cid in enumerate(cell_ids)}

    criminal_set = {1, 4, 7, 10, 13, 16, 19, 22, 25, 8}
    innocent_set = set(range(1, 26)) - criminal_set

    clauses = []
    for v in sorted(criminal_set):
        clauses.append([v])
    for v in sorted(innocent_set):
        clauses.append([-v])

    snap = KnowledgeBaseSnapshot(
        clauses=clauses,
        primary_vars={f"C_{cid}": var for cid, var in cell_to_var.items()},
        unresolved_cell_ids=list(cell_ids),
        cell_to_var=cell_to_var,
        active_clue_ids=["clue1"],
        known_statuses={},
        aux_var_count=0,
    )
    return "Synthetic 5x5", snap, "5x5"


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    name: str,
    snapshot: KnowledgeBaseSnapshot,
    grid_size: str,
) -> BenchmarkResult:
    """Run a full benchmark on a single puzzle snapshot."""
    agent = DeductiveAgent()

    # 1. Classify all
    t0 = time.perf_counter()
    result = agent.classify_all(snapshot)
    classify_time = (time.perf_counter() - t0) * 1000

    # 2. Uniqueness check
    t1 = time.perf_counter()
    is_unique, uniq_metrics = agent.check_uniqueness(snapshot)
    uniq_time = (time.perf_counter() - t1) * 1000

    forced = sum(1 for v in result.classifications.values() if v != "UNKNOWN")
    unknown = sum(1 for v in result.classifications.values() if v == "UNKNOWN")

    total_sat_calls = result.metrics.sat_calls + uniq_metrics.sat_calls
    total_decisions = result.metrics.total_decisions + uniq_metrics.total_decisions
    total_propagations = result.metrics.total_propagations + uniq_metrics.total_propagations
    total_backtracks = result.metrics.total_backtracks + uniq_metrics.total_backtracks

    return BenchmarkResult(
        name=name,
        grid_size=grid_size,
        num_primary_vars=len(snapshot.cell_to_var),
        num_aux_vars=snapshot.aux_var_count,
        num_clauses=snapshot.clause_count,
        sat_calls=total_sat_calls,
        decisions=total_decisions,
        propagations=total_propagations,
        backtracks=total_backtracks,
        deduction_steps=len(result.trace),
        forced_count=forced,
        unknown_count=unknown,
        is_consistent=result.is_consistent,
        is_unique=is_unique,
        total_runtime_ms=classify_time + uniq_time,
    )


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------

_CSV_HEADERS = [
    "Name", "Grid", "Primary Vars", "Aux Vars", "Clauses",
    "SAT Calls", "Decisions", "Propagations", "Backtracks",
    "Deduction Steps", "Forced", "Unknown",
    "Consistent", "Unique", "Runtime (ms)",
]


def _result_to_row(r: BenchmarkResult) -> List:
    return [
        r.name, r.grid_size, r.num_primary_vars, r.num_aux_vars,
        r.num_clauses, r.sat_calls, r.decisions, r.propagations,
        r.backtracks, r.deduction_steps, r.forced_count, r.unknown_count,
        r.is_consistent, r.is_unique, f"{r.total_runtime_ms:.3f}",
    ]


def export_csv(results: List[BenchmarkResult], path: Path) -> None:
    """Write results to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(_CSV_HEADERS)
        for r in results:
            writer.writerow(_result_to_row(r))
    print(f"  -> CSV saved to {path.relative_to(_PROJECT_ROOT)}")


def export_markdown(results: List[BenchmarkResult], path: Path) -> None:
    """Write results to a Markdown table file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    col_widths = [max(len(h), 12) for h in _CSV_HEADERS]

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Experiment Results\n\n")
        f.write("Generated by `experiments.py`.\n\n")

        header = "| " + " | ".join(h.ljust(w) for h, w in zip(_CSV_HEADERS, col_widths)) + " |\n"
        sep = "| " + " | ".join("-" * w for w in col_widths) + " |\n"
        f.write(header)
        f.write(sep)

        for r in results:
            row = _result_to_row(r)
            line = "| " + " | ".join(str(v).ljust(w) for v, w in zip(row, col_widths)) + " |\n"
            f.write(line)

        f.write("\n## Summary\n\n")
        for r in results:
            f.write(
                f"- **{r.name}** ({r.grid_size}): "
                f"{r.sat_calls} SAT calls, "
                f"{r.num_clauses} clauses, "
                f"{r.total_runtime_ms:.3f} ms\n"
            )

    print(f"  -> Markdown saved to {path.relative_to(_PROJECT_ROOT)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  Griductive DPLL & Agent — Benchmark Experiments")
    print("=" * 70)

    puzzles_dir = _PROJECT_ROOT / "puzzles"
    demo_files = [
        puzzles_dir / "gui_demo_3x3.json",
        puzzles_dir / "gui_demo_4x4.json",
        puzzles_dir / "gui_demo_5x5.json",
    ]

    benchmarks_to_run = []

    # Thử nạp từ các file JSON puzzle thực tế qua CNFEncoder
    for p_path in demo_files:
        if p_path.exists():
            try:
                name, snap, grid_size = _load_puzzle_from_json(p_path)
                benchmarks_to_run.append((name, snap, grid_size))
            except Exception as e:
                print(f"[Bỏ qua {p_path.name}] {e}")

    # Fallback sang synthetic benchmarks nếu không tìm thấy file JSON chứa clue hợp lệ
    if not benchmarks_to_run:
        print("\n[Thông báo] Đang chạy bộ synthetic benchmarks chuẩn với đầy đủ các clause CNF...")
        benchmarks_to_run = [
            _generate_3x3_synthetic(),
            _generate_4x4_synthetic(),
            _generate_5x5_synthetic(),
        ]

    results: List[BenchmarkResult] = []

    for name, snapshot, grid_size in benchmarks_to_run:
        print(f"\n>> Running: {name} ({grid_size})")
        print(
            f"  Clauses: {snapshot.clause_count}, "
            f"Primary vars: {len(snapshot.cell_to_var)}, "
            f"Aux vars: {snapshot.aux_var_count}"
        )

        br = run_benchmark(name, snapshot, grid_size)
        results.append(br)

        print(f"  SAT calls:     {br.sat_calls}")
        print(f"  Decisions:     {br.decisions}")
        print(f"  Propagations:  {br.propagations}")
        print(f"  Backtracks:    {br.backtracks}")
        print(f"  Forced/Unknown: {br.forced_count}/{br.unknown_count}")
        print(f"  Consistent:    {br.is_consistent}")
        print(f"  Unique:        {br.is_unique}")
        print(f"  Runtime:       {br.total_runtime_ms:.3f} ms")

    # Export
    out_dir = _PROJECT_ROOT / "output" / "experiments"
    export_csv(results, out_dir / "results.csv")
    export_markdown(results, out_dir / "results.md")

    print("\n" + "=" * 70)
    print("  All benchmarks complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()