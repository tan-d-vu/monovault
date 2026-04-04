# Requirements

MonoVault has the following Python dependencies.

## Installation

Install all dependencies:
```bash
pip install -r requirements.txt
```

Or install with development dependencies:
```bash
pip install -e ".[dev]"
```

## Dependencies

### Core Dependencies (Required for running MonoVault)

| Package | Version | Purpose |
|---------|---------|---------|
| **PyQt6** | >=6.6.0 | GUI framework for the desktop application |
| **mutagen** | >=1.47.0 | Audio metadata reading/writing (MP3, FLAC, etc.) |

### Development Dependencies (Required for development/testing)

| Package | Version | Purpose |
|---------|---------|---------|
| **pyinstaller** | >=6.0.0 | Build standalone executables |
| **pytest** | >=7.0.0 | Test framework |
| **pytest-cov** | >=4.0.0 | Code coverage for tests |
| **ruff** | >=0.1.0 | Code linter and formatter |

## Python Version

MonoVault requires **Python 3.10 or higher**.

## Installing from Source

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python -m src.ui.main_window
   ```

## For Development

Install development dependencies:
```bash
pip install -e ".[dev]"
```

Then use the available commands:
```bash
pytest                  # Run tests
ruff check src/ tests/  # Lint code
ruff format src/ tests/ # Format code
pyinstaller --onefile --windowed src/ui/main_window.py  # Build executable
```
