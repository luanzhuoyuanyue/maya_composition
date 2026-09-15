# Task 7 validation fix 4 report

Baseline: `9c7466b` (`fix: use RGBA image plane display mode`).

## Cause and change

The Maya 2025 interactive result records `QImage.save(path, "PNG")` returning
false even though an independently decoded 960x540 RGBA file exists. The
controller previously treated that boolean as an all-or-nothing success signal.

`composition_guides.py` now records the save result, then makes the file's
postconditions authoritative. `_is_valid_written_png` requires a nonempty file
and a fresh `QImage(path)` that is non-null, matches the requested width and
height, and has an alpha channel. A false Qt save result is accepted only after
those checks; every invalid postcondition still raises the existing `GuideError`.

## TDD evidence

The focused Maya 2025 test run before the implementation was red:

- false save plus a valid reload raised `GuideError`;
- true save plus a null reload was incorrectly accepted.

The regression coverage uses a real temporary output path and controlled Qt
reload outcomes. It covers true/false save with a valid reload, and rejects
false save with a missing, empty, null, wrong-width, wrong-height, or
no-alpha result, plus true save with an invalid reload.

## Verification

Both installed Maya Python environments completed the full suite and bytecode
compilation successfully:

- Maya 2023 mayapy: 94 tests passed; `compileall -q .` exit 0.
- Maya 2025 mayapy: 94 tests passed; `compileall -q .` exit 0.

The real interactive GUI probe was not rerun here. Its pre-fix result remains
the evidence for the false-negative scenario; a controller will perform that
GUI validation separately.
