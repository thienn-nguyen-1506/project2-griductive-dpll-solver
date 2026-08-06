# Griductive GUI Template

This repository currently contains a GUI-first template for the Griductive
course project. It uses demo public data so the interface can be designed before
the real Game Engine, CNF encoder, and Deductive Agent are ready.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py
```

The selected Python installation must include Tkinter. Check it with:

```bash
python3 -c "import tkinter; print(tkinter.TkVersion)"
```

If that import fails, use a Python distribution that includes Tk support before
installing `requirements.txt`.

## What the template already demonstrates

- Dynamic grid coordinates and 4x4 demo cards.
- Face-up and face-down card states.
- Criminal, Innocent, Unknown, selected, hint, and clue-highlight states.
- Manual verdict buttons with ACCEPTED, NOT_PROVABLE, and CONTRADICTED demos.
- Revealed clue selection and referenced-cell highlighting.
- Load, Restart, Hint, Auto Solve, and deduction trace controls.
- Light, dark, and system appearance modes.
- A public-state boundary: the GUI model contains no hidden solution or
  unrevealed clue text.

## Try the demo interactions

- Select `B2`, then submit `Criminal` to see ACCEPTED.
- Select `B2`, then submit `Innocent` to see CONTRADICTED.
- Select most other unresolved cells to see NOT_PROVABLE.
- Click a revealed clue to highlight its referenced cells.
- Use Hint and Auto Solve to exercise their integration points.

## Integration contract

The GUI talks only to the `GameGateway` protocol in `gui/models.py`. During
development it uses `MockGameGateway`. Replace that class with an adapter around
the team's real Game Engine while preserving these methods:

```python
get_public_state()
submit_verdict(cell_id, status)
get_hint()
auto_solve_step()
restart()
load_puzzle(path)
```

The returned `GameView` must contain only public information. Do not add hidden
statuses or unrevealed clue content to `CellView`.

## Main customization points

- Colors and visual tokens: `gui/theme.py`
- Layout and widgets: `gui/app.py`
- Demo behavior: `gui/mock_engine.py`
- Public data contracts: `gui/models.py`

The next integration step is to create a real gateway adapter that converts the
team's Game Engine state into `GameView` and forwards GUI actions back to the
engine.
