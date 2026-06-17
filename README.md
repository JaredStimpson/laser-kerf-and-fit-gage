# Laser Kerf And Fit Gage

GUI-first Python desktop app for generating laser-cut calibration files for LightBurn and similar workflows.

The app has two separate tools:

- Kerf / cutter compensation tester
- Fit allowance tester

The point is to keep machine/process kerf separate from desired mechanical fit allowance. Use the kerf tester to dial in your laser/process compensation first, then use the fit allowance tester to choose the intentional clearance or interference you want in real parts.

Each tool screen has:

- A live preview pane showing the geometry that will be generated
- A `General` tab for the controls used most often
- An `Advanced` tab for less-common placement, tick, label, and strip layout dimensions
- Hover/focus help that highlights the dimension controlled by the active setting

## Windows Quick Start

From the repo root:

```powershell
.\setup.bat
.\run.bat
```

The setup script creates a local `.venv`, verifies Python 3.10+, and checks that Tkinter is available. The run script always launches through `.venv\Scripts\python.exe`, so you do not have to double-click a file or guess which Python Windows will choose.

If Python is not on PATH, pass it explicitly:

```powershell
.\setup.bat -Python "C:\Path\To\python.exe"
```

You can also set `PYTHON_EXE` before running setup/run/test:

```powershell
$env:PYTHON_EXE = "C:\Path\To\python.exe"
.\setup.bat
```

Run tests with:

```powershell
.\test.bat
```

Generate sample SVG/DXF/JSON files without opening the GUI:

```powershell
.\run.bat --sample-dir samples
```

## Outputs

Each tester can export:

- SVG
- DXF

SVG files use a millimeter viewBox and simple strokes. DXF files use basic R12-compatible `LINE` and `TEXT` entities with `$INSUNITS` set to millimeters.

Layers:

- `CUT`: red cut geometry
- `MARK`: black score/text geometry, labels, scale ticks, and reference marks

## Parameter Files

Use `Save Params` and `Load Params` in the app. These are JSON parameter files, not generated output files.

By default, parameter files are opened from:

```text
Documents\Laser Tester Generator Parameters
```

Generated output defaults to:

```text
Documents\Laser Tester Generator Exports
```

## Kerf Tester

The kerf tester draws a Vernier-style kerf offset finder. It has a row of loose sliding pieces, a lower slide channel, a right-hand `DISCARD` tab, a top `D` scale, and a bottom `E` vernier scale.

The `DISCARD` clearance is sized in whole top-row piece widths, and the slider end uses a diagonal nose cut so the slider has room to move right after the discard piece is removed.

Suggested use:

1. Cut with your usual cut and score settings, with kerf offset disabled in the cutter settings.
2. Remove the loose pieces and the piece marked `DISCARD`.
3. Slide the loose pieces to the right.
4. Read the largest whole number crossed by the `D` line on the top scale.
5. Find the bottom `E` vernier line that best aligns with a border line.
6. Use the printed equation, `Kerf offset = D.E / 40`, unless you changed the denominator setting.

The default `/40` denominator is a ready-to-try starting point based on the Vernier reference style. Confirm the result with your machine, material, cut direction, and LightBurn compensation settings.

## Fit Allowance Tester

The fit allowance tester draws:

- A long strip with fit holes
- One matching pin coupon

Each hole has two separate dimensions:

```text
horizontal hole dimension = material thickness + thickness clearance
vertical hole dimension = nominal pin width + controlled allowance
```

The matching pin uses the material thickness and nominal pin width directly. Changing thickness clearance only changes the holes, not the pin.

The labels under the holes are controlled allowance values in millimeters. Negative values make the vertical fit tighter. Positive values make it looser.
