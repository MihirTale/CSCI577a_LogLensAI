#!/usr/bin/env python3
"""
Data Loading Pipeline - Step 1
Triggers a real Out-of-Memory error by attempting to allocate an
impossibly large NumPy array — the same failure seen in production
when a data loader reads a multi-gigabyte CSV entirely into RAM
instead of streaming it in chunks.
"""

import subprocess
import sys


def install(package: str) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])


def load_dataset(filename: str):
    import numpy as np

    print(f"[INFO] Opening file: {filename}")
    print("[INFO] Estimated file size: 52.4 GB")
    print("[INFO] Allocating in-memory buffer for full dataset load...")

    rows = 10_000_000_000   # 10 billion rows
    cols = 1_000
    required_tb = rows * cols * 8 / 1e12

    print(f"[INFO] Requested shape  : ({rows:,} rows × {cols} cols) float64")
    print(f"[INFO] Required memory  : {required_tb:.0f} TB")
    print("[INFO] Allocating ...")

    # numpy's allocator raises a real MemoryError:
    # "Unable to allocate X TiB for an array with shape (...) and data type float64"
    return np.zeros((rows, cols), dtype=np.float64)


if __name__ == "__main__":
    print("[INFO] ============================================================")
    print("[INFO]  Step 1: Load Training Dataset")
    print("[INFO] ============================================================")
    print("[INFO] Script      : data_loader.py")
    print("[INFO] Purpose     : Load full training data for downstream model training")
    print("[INFO] Source file : training_data_2024_v2.csv")
    print()

    print("[INFO] Installing numpy ...")
    install("numpy")

    dataset = load_dataset("training_data_2024_v2.csv")
    print(f"[INFO] Successfully loaded {dataset.shape[0]:,} rows.")
    print("[INFO] Step 1 PASSED.")
