#!/usr/bin/env python3
"""
Model Serving Pipeline - Step 3
Triggers a real KeyError by accessing required environment variables with
os.environ[] rather than .get() — the same crash seen in production when
a secret exists locally but was never added to the CI secrets store.
"""

import os
import sys


REQUIRED_ENV_VARS = [
    "MODEL_SERVING_ENDPOINT",
    "MODEL_API_SECRET_KEY",
    "INFERENCE_TIMEOUT_MS",
    "FEATURE_STORE_DSN",
]


def validate_environment() -> dict:
    """
    Read all required environment variables.
    os.environ[key] raises a real KeyError if the variable is not set.
    """
    config = {}
    for var in REQUIRED_ENV_VARS:
        print(f"[INFO] Reading {var} ...")
        config[var] = os.environ[var]   # real KeyError raised by Python if missing
    return config


def connect_model_endpoint(config: dict) -> None:
    endpoint = config["MODEL_SERVING_ENDPOINT"]
    print(f"[INFO] Connecting to model endpoint: {endpoint}")
    print("[INFO] Authenticating with MODEL_API_SECRET_KEY...")
    print(f"[INFO] Timeout configured: {config['INFERENCE_TIMEOUT_MS']} ms")
    print(f"[INFO] Feature store DSN  : {config['FEATURE_STORE_DSN']}")
    print("[INFO] Connection established.")


if __name__ == "__main__":
    print("[INFO] ============================================================")
    print("[INFO]  Step 3: Model Serving — Environment Validation")
    print("[INFO] ============================================================")
    print("[INFO] Script  : model_server.py")
    print("[INFO] Purpose : Connect to model serving endpoint and validate runtime config")
    print()

    config = validate_environment()
    connect_model_endpoint(config)
    print("[INFO] Step 3 PASSED.")
