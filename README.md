# Nightfall Vehicle BIN Analyser

Open-source vehicle ECU BIN analysis and calibration tooling developed by Nightfall Automotive.

The project is intended for automotive technicians, calibration developers, researchers and enthusiasts who want to inspect ECU binary files and experiment with automated calibration analysis.

## Features

- ECU BIN file analysis
- Calibration identification
- Map and data structure analysis
- Comparison of original and modified BIN files
- Calibration definition support
- Test BIN files for development
- Damos/calibration definition files for tester development

## Installation

Clone the repository:

    git clone https://github.com/NightfallAutomotive/nightfall-vehicle-bin-analyser.git

Enter the project directory:

    cd nightfall-vehicle-bin-analyser

Create a Python virtual environment:

    python -m venv .venv

Activate it on Windows:

    .venv\Scripts\activate

Install the required packages:

    pip install -r requirements.txt

## Usage

The analyser can be run using the included application and analysis scripts.

Refer to the source code and test_analyser.py for examples of the currently supported functionality.

Run the tests (requires `pip install pytest`):

    python -m pytest

Print an analysis report for the included test BIN pairs:

    python test_analyser.py

## Checking a Single File

Upload one file on its own to find out what has been done to it: torque
limiter changes, a raised speed limiter, on/off switches, and fault checks
switched off (with the fault codes, where the ECU layout allows it).

The analyser reads the file's Bosch software number and compares it with the
stock original for that number from a library on the server. Without a
match it falls back to pattern checks, which can only report the torque
limiter maps in the file.

The library is a folder of stock reads, set with `NIGHTFALL_ORI_LIBRARY`
(default `./library`, which git ignores). Fill it from a WinOLS job
database; files are named by software number and hash, so no registrations,
VINs or customer names are copied:

    python build_library.py "/path/to/WinOLS Database" --dry-run
    python build_library.py "/path/to/WinOLS Database"

Only add reads you know are stock: a car that was tuned before it was read
gives a misleading original.

When someone uploads an original together with a modified file, the original
is also saved, in `library/uploads`, so that software can be checked on its
own next time. The page tells people this and lets them opt out. Only the
contents are kept, named by software number and hash, never the uploaded
filename. Curated originals are preferred over uploaded ones, since an
uploaded "original" may already have been tuned. On a hosted server, keep the
library on persistent storage so it survives restarts and redeploys.

## Deploying

The analyser is a Python (FastAPI) server, so it needs a host that runs
Python; static hosts such as Netlify or GitHub Pages can't run it.

`render.yaml` sets it up on [Render](https://render.com): in the Render
dashboard choose **New > Blueprint** and pick this repository. It builds with
`pip install -r requirements.txt`, starts with
`uvicorn app:app --host 0.0.0.0 --port $PORT`, and redeploys on every push.

The stock-original library lives on a persistent disk mounted at
`/var/data` (`NIGHTFALL_ORI_LIBRARY=/var/data/library`), which needs a paid
plan. On the free plan, remove the `disk` block and set `plan: free`; the
analyser works the same, but saved originals are lost whenever it restarts.

To add your curated originals, build the library locally with
`build_library.py` and copy the folder to `/var/data/library` on the server
(Render's SSH access supports `scp`).

Any other Python host works the same way: install the requirements, set
`NIGHTFALL_ORI_LIBRARY` to a folder on persistent storage, and run the
uvicorn command above.

## Test Files

The `test-files` directory contains anonymous ECU BIN files that can be used when testing and developing the analyser.

These files are included to make it easier for contributors to reproduce and test analyser behaviour.

## Damos Files

The `damos` directory is intended for publicly distributable Damos/calibration definition files used for testing and development.

Only add files that you have permission to redistribute publicly.

## Contributing

Contributions are welcome.

You can fork the repository, make your changes and submit a pull request.

Useful contributions include:

- New ECU support
- Improved calibration detection
- Additional map detection
- Improved BIN comparison
- New test cases
- Bug fixes
- Documentation improvements

Please include appropriate test files or test cases where possible when adding new functionality.

## Disclaimer

This software is provided for research, development and diagnostic purposes.

ECU calibration changes can affect vehicle performance, emissions, reliability and legal compliance.

Always ensure that any calibration or modification is appropriate for the vehicle and complies with applicable laws and regulations.

Nightfall Automotive accepts no responsibility for damage, loss or other consequences resulting from the use of this software or files provided with the project.

## Licence

This project is released under the MIT Licence.

See `LICENSE` for the full licence text.
