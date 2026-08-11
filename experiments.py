"""Benchmark experiments for DPLL SAT Solver and Deductive Agent.

This script provides:
* **Fallback synthetic CNF benchmarks** for DPLL-only and Agent testing in
  isolation (does not require Engine or CNF Encoder).
* Hooks for loading **real benchmark puzzles** provided by Engine/CNF members.
* Exports results to CSV and Markdown for the report.

Usage
-----
    python experiments.py                 # run all synthetic benchmarks
    python experiments.py --puzzle PATH   # run with a real puzzle (future)

Output
------
    output/experiments/results.csv
    output/experiments/results.md
"""

from __future__ import annotations

import csv
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure project root is on sys.path so core package is importable.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.dpll import DPLLSolver  # noqa: E402
from core.agent import (  # noqa: E402
    DeductiveAgent,
    KnowledgeBaseSnapshot,
)


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
# Synthetic puzzle generators
# ---------------------------------------------------------------------------

def _generate_3x3_synthetic() -> Tuple[str, KnowledgeBaseSnapshot]:
    """Synthetic 3×3 puzzle (9 cells) with hand-crafted CNF.

    Grid layout:
        A1 B1 C1
        A2 B2 C2
        A3 B3 C3

    Hidden truth: A1=C, B1=I, C1=I, A2=I, B2=C, C2=I, A3=I, B3=I, C3=C
    (3 criminals, 6 innocents)

    Clues encoded as CNF:
    1. FACT: A1 is Criminal → unit clause [1]
    2. EXACTLY 1 criminal in row 1 {A1,B1,C1}: since A1=C, B1 and C1 must be I
       → [-2], [-3]
    3. SAME status for B2 and C3 → (B2↔C3): (-5∨9)∧(5∨-9)
    4. DIFFERENT status for A2 and B2 → (A2 ⊕ B2): (-4∨-5)∧(4∨5)
    5. AT_LEAST 1 criminal in column B {B1,B2,B3}: (2∨5∨8)
    6. AT_MOST 1 criminal in row 3 {A3,B3,C3}: (-7∨-8)∧(-7∨-9)∧(-8∨-9)
    """
    cell_ids = ["A1", "B1", "C1", "A2", "B2", "C2", "A3", "B3", "C3"]
    cell_to_var = {cid: i + 1 for i, cid in enumerate(cell_ids)}
    # Vars: A1=1, B1=2, C1=3, A2=4, B2=5, C2=6, A3=7, B3=8, C3=9

    clauses = [
        [1],             # FACT: A1 is Criminal
        [-2],            # EXACTLY 1 criminal in row1 (given A1=C)
        [-3],            # EXACTLY 1 criminal in row1 (given A1=C)
        [-5, 9],         # SAME: B2 ↔ C3  (part 1)
        [5, -9],         # SAME: B2 ↔ C3  (part 2)
        [-4, -5],        # DIFFERENT: A2 ⊕ B2 (part 1)
        [4, 5],          # DIFFERENT: A2 ⊕ B2 (part 2)
        [2, 5, 8],       # AT_LEAST 1 criminal in col B
        [-7, -8],        # AT_MOST 1 criminal in row 3 (pair 1)
        [-7, -9],        # AT_MOST 1 criminal in row 3 (pair 2)
        [-8, -9],        # AT_MOST 1 criminal in row 3 (pair 3)
        [-6],            # Extra: C2 is Innocent (helps force unique solution)
    ]

    snap = KnowledgeBaseSnapshot(
        clauses=clauses,
        primary_vars={f"C_{cid}": var for cid, var in cell_to_var.items()},
        unresolved_cell_ids=list(cell_ids),
        cell_to_var=cell_to_var,
        active_clue_ids=["clue1", "clue2", "clue3", "clue4", "clue5", "clue6"],
        known_statuses={},
        aux_var_count=0,
    )
    return "Synthetic 3x3", snap


def _generate_4x4_synthetic() -> Tuple[str, KnowledgeBaseSnapshot]:
    """Synthetic 4x4 puzzle (16 cells) with hand-crafted CNF.

    Grid layout:
        A1 B1 C1 D1
        A2 B2 C2 D2
        A3 B3 C3 D3
        A4 B4 C4 D4

    Hidden truth: A1=C, B1=I, C1=I, D1=C,
                  A2=I, B2=C, C2=I, D2=I,
                  A3=I, B3=I, C3=C, D3=I,
                  A4=C, B4=I, C4=I, D4=C
    (6 criminals, 10 innocents)
    """
    cell_ids = [f"{c}{r}" for r in range(1, 5) for c in "ABCD"]
    cell_to_var = {cid: i + 1 for i, cid in enumerate(cell_ids)}
    # A1=1,B1=2,C1=3,D1=4, A2=5,B2=6,C2=7,D2=8,
    # A3=9,B3=10,C3=11,D3=12, A4=13,B4=14,C4=15,D4=16

    clauses = [
        # FACT clues
        [1],              # A1 is Criminal
        [-2],             # B1 is Innocent
        [4],              # D1 is Criminal
        [-5],             # A2 is Innocent
        [6],              # B2 is Criminal
        [-7],             # C2 is Innocent
        [-8],             # D2 is Innocent
        [-9],             # A3 is Innocent
        [-10],            # B3 is Innocent
        [11],             # C3 is Criminal
        [-12],            # D3 is Innocent
        [13],             # A4 is Criminal
        [-14],            # B4 is Innocent
        [-15],            # C4 is Innocent
        [16],             # D4 is Criminal

        # EXACTLY 2 criminals in row 1: (1+2+3+4)=2
        # Since A1=C, D1=C forced above, also need ¬B1∧¬C1 (already have [-2],[-3] effective)
        [-3],             # C1 is Innocent (consistent with exactly 2 in row1)

        # SAME: A4 ↔ D4 (both criminal)
        [-13, 16],
        [13, -16],

        # DIFFERENT: B2 ⊕ C3 – but both are criminal in truth → this would
        # fail.  Instead: DIFFERENT B1 ⊕ B2
        [-2, -6],
        [2, 6],

        # AT_LEAST 1 criminal in col C: (3∨7∨11∨15)
        [3, 7, 11, 15],

        # AT_MOST 2 criminals in col A: pairs of 3 from {1,5,9,13}
        # Since exactly 2 are criminal (1,13), all triples must not all be true.
        [-1, -5, -9],
        [-1, -5, -13],
        [-1, -9, -13],
        [-5, -9, -13],
    ]

    snap = KnowledgeBaseSnapshot(
        clauses=clauses,
        primary_vars={f"C_{cid}": var for cid, var in cell_to_var.items()},
        unresolved_cell_ids=list(cell_ids),
        cell_to_var=cell_to_var,
        active_clue_ids=[f"clue{i}" for i in range(1, 9)],
        known_statuses={},
        aux_var_count=0,
    )
    return "Synthetic 4x4", snap


def _generate_5x5_synthetic() -> Tuple[str, KnowledgeBaseSnapshot]:
    """Synthetic 5x5 puzzle (25 cells) with hand-crafted CNF.

    Grid:
        A1 B1 C1 D1 E1
        A2 B2 C2 D2 E2
        A3 B3 C3 D3 E3
        A4 B4 C4 D4 E4
        A5 B5 C5 D5 E5

    Hidden truth:
        Row 1: C  I  I  C  I
        Row 2: I  C  I  I  C
        Row 3: I  I  C  I  I
        Row 4: C  I  I  C  I
        Row 5: I  C  I  I  C
    (10 criminals, 15 innocents)
    """
    cell_ids = [f"{c}{r}" for r in range(1, 6) for c in "ABCDE"]
    cell_to_var = {cid: i + 1 for i, cid in enumerate(cell_ids)}
    # A1=1..E1=5, A2=6..E2=10, A3=11..E3=15, A4=16..E4=20, A5=21..E5=25

    # For a 5x5 we provide more unit clauses to keep the benchmark focused
    # on DPLL performance rather than encoding complexity.
    criminal_vars = [1, 4, 7, 10, 13, 16, 19, 22, 25, 8]  # deliberately not sorted
    # Correct criminals by cell: A1(1),D1(4),B2(7),E2(10),C3(13),A4(16),D4(19),B5(22),E5(25)
    # Wait, let me recount: cells A1=1,B1=2,C1=3,D1=4,E1=5
    # A2=6,B2=7,C2=8,D2=9,E2=10
    # A3=11,B3=12,C3=13,D3=14,E3=15
    # A4=16,B4=17,C4=18,D4=19,E4=20
    # A5=21,B5=22,C5=23,D5=24,E5=25
    # Truth: A1=C(1),D1=C(4),B2=C(7),E2=C(10),C3=C(13),A4=C(16),D4=C(19),B5=C(22),E5=C(25)
    # That's 9 criminals. Let's add C2=C(8) → 10 criminals.
    # Actually let's just define it cleanly:

    criminal_set = {1, 4, 7, 10, 13, 16, 19, 22, 25, 8}
    innocent_set = set(range(1, 26)) - criminal_set

    clauses = []

    # Unit clauses for all cells (fully determined puzzle for benchmark).
    for v in sorted(criminal_set):
        clauses.append([v])
    for v in sorted(innocent_set):
        clauses.append([-v])

    # Add some redundant structural clauses to make DPLL work harder.
    # EXACTLY 2 criminals in row 1: {1,2,3,4,5}
    # At least 2: all pairs must have at least one (C(5,2)=10 clauses too many).
    # Instead add simpler constraints:
    # AT_LEAST 1 criminal per row.
    for r in range(5):
        row_vars = list(range(r * 5 + 1, r * 5 + 6))
        clauses.append(row_vars)  # at least one criminal in row

    # AT_MOST 3 criminals per row (all 4-subsets must not all be true).
    for r in range(5):
        row_vars = list(range(r * 5 + 1, r * 5 + 6))
        # Every 4-subset negated.
        from itertools import combinations
        for combo in combinations(row_vars, 4):
            clauses.append([-v for v in combo])

    # SAME constraints.
    # A1 ↔ A4 (both criminal).
    clauses.append([-1, 16])
    clauses.append([1, -16])
    # B2 ↔ B5 (both criminal).
    clauses.append([-7, 22])
    clauses.append([7, -22])

    snap = KnowledgeBaseSnapshot(
        clauses=clauses,
        primary_vars={f"C_{cid}": var for cid, var in cell_to_var.items()},
        unresolved_cell_ids=list(cell_ids),
        cell_to_var=cell_to_var,
        active_clue_ids=[f"clue{i}" for i in range(1, 12)],
        known_statuses={},
        aux_var_count=0,
    )
    return "Synthetic 5x5", snap


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

    # 1. Classify all.
    t0 = time.perf_counter()
    result = agent.classify_all(snapshot)
    classify_time = (time.perf_counter() - t0) * 1000

    # 2. Uniqueness check.
    t1 = time.perf_counter()
    is_unique, uniq_metrics = agent.check_uniqueness(snapshot)
    uniq_time = (time.perf_counter() - t1) * 1000

    forced = sum(
        1 for v in result.classifications.values() if v != "UNKNOWN"
    )
    unknown = sum(
        1 for v in result.classifications.values() if v == "UNKNOWN"
    )

    # Combine metrics.
    total_sat_calls = result.metrics.sat_calls + uniq_metrics.sat_calls
    total_decisions = (result.metrics.total_decisions
                       + uniq_metrics.total_decisions)
    total_propagations = (result.metrics.total_propagations
                          + uniq_metrics.total_propagations)
    total_backtracks = (result.metrics.total_backtracks
                        + uniq_metrics.total_backtracks)

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
    print(f"  -> CSV saved to {path.name}")


def export_markdown(results: List[BenchmarkResult], path: Path) -> None:
    """Write results to a Markdown table file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    col_widths = [max(len(h), 12) for h in _CSV_HEADERS]

    with open(path, "w", encoding="utf-8") as f:
        f.write("# Experiment Results\n\n")
        f.write(f"Generated by `experiments.py`.\n\n")

        # Header row.
        header = "| " + " | ".join(
            h.ljust(w) for h, w in zip(_CSV_HEADERS, col_widths)
        ) + " |\n"
        sep = "| " + " | ".join(
            "-" * w for w in col_widths
        ) + " |\n"
        f.write(header)
        f.write(sep)

        # Data rows.
        for r in results:
            row = _result_to_row(r)
            line = "| " + " | ".join(
                str(v).ljust(w) for v, w in zip(row, col_widths)
            ) + " |\n"
            f.write(line)

        # Summary.
        f.write("\n## Summary\n\n")
        for r in results:
            f.write(f"- **{r.name}** ({r.grid_size}): "
                    f"{r.sat_calls} SAT calls, "
                    f"{r.decisions} decisions, "
                    f"{r.propagations} propagations, "
                    f"{r.backtracks} backtracks, "
                    f"{r.total_runtime_ms:.3f} ms\n")

    print(f"  -> Markdown saved to {path.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("  Griductive DPLL & Agent — Benchmark Experiments")
    print("=" * 70)

    # Synthetic benchmarks (fallback – always available).
    generators = [
        (_generate_3x3_synthetic, "3x3"),
        (_generate_4x4_synthetic, "4x4"),
        (_generate_5x5_synthetic, "5x5"),
    ]

    results: List[BenchmarkResult] = []

    for gen_fn, grid_size in generators:
        name, snapshot = gen_fn()
        print(f"\n>> Running: {name} ({grid_size})")
        print(f"  Clauses: {snapshot.clause_count}, "
              f"Primary vars: {len(snapshot.cell_to_var)}, "
              f"Aux vars: {snapshot.aux_var_count}")

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

    # Export.
    out_dir = _PROJECT_ROOT / "output" / "experiments"
    export_csv(results, out_dir / "results.csv")
    export_markdown(results, out_dir / "results.md")

    print("\n" + "=" * 70)
    print("  All benchmarks complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()
