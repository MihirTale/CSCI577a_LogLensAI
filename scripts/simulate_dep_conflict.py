#!/usr/bin/env python3
"""
Dependency Resolution Pipeline - Step 4
Creates a real dependency conflict by installing genuinely incompatible
package versions and then triggering the resulting ImportError.

Conflict scenario:
  - pandas==2.1.4 wheels are compiled against the numpy 1.x C API
  - numpy==2.0.0 introduced breaking C-ABI changes (array descriptor layout,
    removed legacy symbols such as _PyArray_LegacyDescr)
  - Importing pandas after force-installing numpy 2.0.0 raises a real
    ImportError from Python's dynamic linker — no raise statement needed
"""

import subprocess
import sys


def install(package: str, *flags: str) -> None:
    """Install *package* using the current interpreter's pip."""
    subprocess.check_call([sys.executable, "-m", "pip", "install", package, *flags])


def run_pipeline() -> None:
    # 1. Install pandas 2.1.4 — C-extensions built against numpy <2.0
    print("[INFO] Installing pandas==2.1.4  (C-extensions require numpy<2.0) ...")
    install("pandas==2.1.4", "--quiet")

    # 2. Force numpy to 2.0.0 — C-ABI incompatible with pandas 2.1.x wheels
    print("[INFO] Force-installing numpy==2.0.0  (introduces C-ABI break) ...")
    install("numpy==2.0.0", "--force-reinstall", "--quiet")

    # 3. Attempt the import — Python's loader raises a real ImportError
    print("[INFO] numpy  installed : OK  (numpy==2.0.0)")
    print("[INFO] Importing pandas ...")
    import pandas  # noqa: F401  — real ImportError raised by Python's import machinery


if __name__ == "__main__":
    print("[INFO] ============================================================")
    print("[INFO]  Step 4: ML Pipeline — Dependency Validation")
    print("[INFO] ============================================================")
    print("[INFO] Script  : ml_trainer.py")
    print("[INFO] Purpose : Validate ML dependency compatibility before training")
    print()

    run_pipeline()
