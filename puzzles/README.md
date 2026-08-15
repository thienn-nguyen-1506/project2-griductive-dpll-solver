# Official puzzle format

Files named `level_*.json` are real engine-owned puzzles. The older
`gui_demo_*.json` files only resize the Mock GUI and are not logical puzzles.

Each official file contains:

- `size`: 3, 4, or 5.
- `initial_revealed`: cards whose statuses and clues form the initial public KB.
- `cells`: exactly `size * size` cells in row-major order.
- Each cell's display name, profession, hidden status, and one structured clue.

Core clue fields use `target_cells` and `value`. The two extensions are:

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
