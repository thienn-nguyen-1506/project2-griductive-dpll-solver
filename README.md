# Griductive Solver

A playable implementation of Project 2 for the Introduction to AI course. The
GUI is connected to the real Game Engine, CNF encoder, DPLL solver, and
Deductive Agent through `RealGameGateway`. Hidden solutions and unrevealed
clues are never exposed through the public game state.

## Installation and Launch on macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 main.py
```

The selected Python installation must include Tkinter. Verify it with:

```bash
python3 -c "import tkinter; print(tkinter.TkVersion)"
```

## Installation on Windows

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Launch on Windows

```bash
.\venv\Scripts\Activate.ps1
python main.py
```

## Dependencies

The project dependencies are declared in `requirements.txt`:

- `customtkinter`: builds the desktop user interface.
- `Pillow`: provides the `PIL` modules used to load and process GUI images.

Do not install a package named `PIL`. Python imports it with
`from PIL import ...`, but the package that must be installed is `Pillow`.

If `ModuleNotFoundError: No module named 'PIL'` appears, make sure the virtual
environment is active and run:

```bash
python3 -m pip install -r requirements.txt
```

On Windows, use the equivalent command:

```bash
python -m pip install -r requirements.txt
```

## Trying the Features

- Select an unsolved card and submit either Criminal or Innocent.
- Use **Hint** to highlight a relevant clue and its referenced cards.
- Use **Next Step** to perform one deduction step.
- Use **Auto Solve** to run deduction continuously; the button becomes **Stop**
  while the solver is running.
- Select a revealed clue to highlight its complete region.
- Use **Choose Level** to select a built-in puzzle, or **Import Puzzle** to load
  an external `level_*.json` file.
- Run `python validate_puzzles.py` to verify clue truth, solution uniqueness,
  and the complete deduction loop for every built-in puzzle.

## Running Experiments

```bash
python3 experiments.py --runs 10 --timeout 5
```

Each puzzle is solved repeatedly through the real deduction loop, starting
only from its initial public knowledge base. Results are written to
`output/experiments/results.csv` and `output/experiments/results.md`. Failed or
timed-out runs are retained as result rows instead of being silently discarded.

## Project Structure

- `gui/app.py`: layout, widgets, and user interactions.
- `gui/theme.py`: colors for Light and Dark modes.
- `gui/models.py`: public data contracts between the GUI and logic components.
- `gui/real_gateway.py`: adapter connecting the GUI to the real Game Engine and
  Deductive Agent.
- `gui/mock_engine.py`: simulated data used only by GUI unit tests.
- `core/puzzle.py`: official puzzle loader and validator.
- `puzzles/level_*.json`: six verified logic puzzles: two 3x3, two 4x4, and two
  5x5 levels.
- `experiments.py`: benchmarks the deduction loop and exports report data.
- `tests/`: tests for the encoder, DPLL solver, agent, experiments, puzzles, and
  gateway integration.
- `GUI_STATUS.md`: current GUI implementation status.
- `GUI_INTEGRATION.md`: instructions for connecting Engine and Agent components
  to the GUI.

## Testing

```bash
python3 -m unittest discover -s tests -v
```

The key architectural rule is that the GUI communicates only through
`GameGateway`. `main.py` provides `RealGameGateway`; the Mock Gateway is never
used in the submitted application's runtime flow.
