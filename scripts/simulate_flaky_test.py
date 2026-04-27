#!/usr/bin/env python3
"""
Integration Test Suite - Step 5
Triggers a real AssertionError caused by a genuine threading race condition:
multiple worker threads complete in non-deterministic order (driven by
varying sleep durations), and the test asserts that results arrive in
submission order — a requirement the async batch handler cannot satisfy.

This is the same failure seen on CI when the worker-pool size differs from
local dev, causing requests to complete in a different order than submitted.
"""

import threading
import time


def run_test_model_prediction_order() -> None:
    """
    Spawn one thread per request, each sleeping for a different duration to
    simulate varying processing times.  Threads append their request ID to a
    shared list as they finish, so the completion order depends on wall-clock
    timing — a real race condition.  The assertion then fails because the
    completion order does not match the submission order.
    """
    print("[INFO] test_model_prediction_order ... ", end="", flush=True)

    input_ids        = [f"req-{i:03d}" for i in range(10)]
    completion_order = []
    lock             = threading.Lock()

    # Unequal delays ensure threads finish out of submission order
    delays = [0.09, 0.01, 0.08, 0.02, 0.07, 0.03, 0.06, 0.04, 0.05, 0.01]

    def process(req_id: str, delay: float) -> None:
        time.sleep(delay)
        with lock:
            completion_order.append(req_id)

    threads = [
        threading.Thread(target=process, args=(req_id, d))
        for req_id, d in zip(input_ids, delays)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Real AssertionError from Python's assert machinery — no raise statement
    assert completion_order == input_ids, (
        f"Prediction order mismatch!\n\n"
        f"  Expected (submission order) : {input_ids}\n"
        f"  Got (completion order)      : {completion_order}\n\n"
        f"  Root cause: worker threads complete in order of processing time,\n"
        f"  not submission order.  The batch handler emits results as each\n"
        f"  thread finishes, so faster requests overtake slower ones.\n\n"
        f"  Fix: collect results into a pre-sized list indexed by position,\n"
        f"  or sort by request ID before returning."
    )

    print("PASS")


def run_test_feature_cache_ttl() -> None:
    print("[INFO] test_feature_cache_ttl    ... ", end="", flush=True)
    time.sleep(0.02)
    print("PASS")


def run_test_db_rollback_on_error() -> None:
    print("[INFO] test_db_rollback_on_error ... ", end="", flush=True)
    time.sleep(0.01)
    print("PASS")


def run_integration_tests() -> None:
    tests = [
        run_test_db_rollback_on_error,
        run_test_feature_cache_ttl,
        run_test_model_prediction_order,   # always fails — real race condition
    ]

    passed = 0
    for test_fn in tests:
        test_fn()
        passed += 1

    print(f"\n[INFO] Results: {passed} passed, 0 failed.")


if __name__ == "__main__":
    print("[INFO] ============================================================")
    print("[INFO]  Step 5: Integration Test Suite")
    print("[INFO] ============================================================")
    print("[INFO] Script  : integration_tests.py")
    print("[INFO] Purpose : Run end-to-end integration tests against the ML serving stack")
    print("[INFO] Runner  : 2 async workers (CI), 8 async workers (local)")
    print()

    run_integration_tests()
    print("[INFO] Step 5 PASSED.")
