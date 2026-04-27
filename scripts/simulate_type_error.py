#!/usr/bin/env python3
"""
Sensor Data Validation Pipeline - Step 2
Triggers a real TypeError by passing a mixed-type list (floats + strings)
to Python's built-in sum() — the same failure seen when IoT sensor
gateways inject string sentinels ('N/A', 'ERROR', 'OFFLINE') for missing
readings instead of NaN.
"""

import sys


def compute_statistics(measurements: list) -> dict:
    """
    Compute basic statistics for a list of numeric measurements.
    Raises a real TypeError if any element is not a number.
    """
    return {
        "mean": sum(measurements) / len(measurements),
        "min": min(measurements),
        "max": max(measurements),
        "count": len(measurements),
    }


def process_sensor_batch(sensor_records: list) -> None:
    print(f"[INFO] Processing {len(sensor_records)} sensor record(s)...")

    for idx, record in enumerate(sensor_records, start=1):
        sensor_id = record.get("sensor_id", f"UNKNOWN-{idx}")
        readings  = record.get("readings", [])
        unit      = record.get("unit", "?")

        print(f"[INFO] Sensor {idx}/{len(sensor_records)}: {sensor_id}")
        print(f"[INFO]   Readings ({len(readings)} values, unit={unit}): {readings}")

        # Python's sum() raises a real TypeError when a string is encountered:
        # "unsupported operand type(s) for +: 'float' and 'str'"
        stats = compute_statistics(readings)

        print(
            f"[INFO]   mean={stats['mean']:.2f} {unit}, "
            f"min={stats['min']}, max={stats['max']}"
        )
        print()


if __name__ == "__main__":
    print("[INFO] ============================================================")
    print("[INFO]  Step 2: Validate & Process Sensor Readings")
    print("[INFO] ============================================================")
    print("[INFO] Script      : sensor_processor.py")
    print("[INFO] Purpose     : Validate IoT sensor readings received via gateway API")
    print("[INFO] Data source : iot-gateway.internal / topic=sensors/temperature")
    print()

    # TEMP-001 is clean; TEMP-002 and TEMP-003 carry string sentinels that
    # the gateway emits for missing readings instead of NaN.
    sensor_data = [
        {
            "sensor_id": "TEMP-001",
            "readings": [23.4, 24.1, 22.8, 25.0, 23.7],
            "unit": "Celsius",
        },
        {
            "sensor_id": "TEMP-002",
            "readings": [21.5, "N/A", 22.3, "ERROR", 21.8, 22.6],
            "unit": "Celsius",
        },
        {
            "sensor_id": "TEMP-003",
            "readings": [19.2, 20.1, "OFFLINE", 19.8],
            "unit": "Celsius",
        },
    ]

    print(f"[INFO] Received {len(sensor_data)} sensor record(s) from IoT gateway.")
    print()

    process_sensor_batch(sensor_data)
    print("[INFO] All sensor records processed successfully.")
    print("[INFO] Step 2 PASSED.")
