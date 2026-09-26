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
