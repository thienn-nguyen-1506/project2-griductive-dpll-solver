# Official puzzle format

Files named `level_*.json` are validated, engine-owned logical puzzles.

Each official file contains:

- `size`: 3, 4, or 5.
- `initial_revealed`: cards whose statuses and clues form the initial public KB.
- `cells`: exactly `size * size` cells in row-major order.
- Each cell's display name, profession, hidden status, and one structured clue.

Named-person clues use `target_cells`. Regional clues may either use an
explicit `target_cells` list or a structured `region` object:

```json
{"kind": "ROW", "row": 2}
{"kind": "COLUMN", "column": "B"}
{"kind": "NEIGHBORS", "cell": "C3"}
{"kind": "EXPLICIT", "cells": ["A1", "C2", "D4"]}
```

The loader resolves the expression to distinct cell IDs, and the encoder
checks that the resolved cells match the declared grid. The two extensions are:

- `PARITY`: `value` is `ODD` or `EVEN`.
- `COUNT_COMPARE`: `left_cells` and `right_cells` are compared using `operator`
  (`GT`, `LT`, `EQ`, `GE`, or `LE`).

Hidden `status` and unrevealed `clue` objects belong to the Game Engine. A GUI
adapter must never include them in its public state before a card is proved.

Validate the complete set with:

```bash
python validate_puzzles.py
```

The validator checks structural parameters, clue truth, uniqueness, and the
entire no-guess deduction loop.

The six built-in levels use non-linear reveal orders. Most deduction waves
make two cards logically available, so the player may choose a valid branch;
`Next Step` only uses row-major order to resolve that choice deterministically.
Later cards generally require a relation clue plus a regional count, rather
than being disclosed by a chain of direct FACT clues.
