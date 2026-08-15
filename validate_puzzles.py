"""Validate every official Griductive puzzle before it is used by the GUI."""

from pathlib import Path

from core.puzzle import load_puzzle, validate_puzzle


def main() -> None:
    project_root = Path(__file__).resolve().parent
    puzzle_files = sorted((project_root / "puzzles").glob("level_*.json"))
    if not puzzle_files:
        raise SystemExit("No official puzzle files were found.")

    for path in puzzle_files:
        puzzle = load_puzzle(path)
        report = validate_puzzle(puzzle)
        order = " -> ".join(report.deduction_order)
        print(f"[OK] {path.name}: {report.message}")
        print(f"     clue types: {', '.join(report.clue_types)}")
        print(f"     deduction: {order}")


if __name__ == "__main__":
    main()
