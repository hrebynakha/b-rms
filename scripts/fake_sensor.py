import argparse
import json
import os
import random
import time
from pathlib import Path

import requests


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
MAC = "ESP32-002"
DEFAULT_PROFILE = Path(__file__).with_name("sensor_profile.json")


def load_profile(path):
    with path.open(encoding="utf-8") as profile_file:
        return json.load(profile_file)


def stage_start_index(args, stage_count):
    if args.start_stage is not None:
        if not 1 <= args.start_stage <= stage_count:
            raise ValueError(
                f"--start-stage must be between 1 and {stage_count}."
            )
        return args.start_stage - 1
    if args.skip_stages is not None:
        if not 0 <= args.skip_stages < stage_count:
            raise ValueError(
                f"--skip-stages must be between 0 and {stage_count - 1}."
            )
        return args.skip_stages
    return 0


def temperature_at(elapsed_seconds, stages):
    stage_start = 0.0
    for stage in stages:
        duration = max(0.1, float(stage["duration_seconds"]))
        if elapsed_seconds <= stage_start + duration:
            progress = (elapsed_seconds - stage_start) / duration
            start = float(stage["start_temperature"])
            end = float(stage["end_temperature"])
            return start + (end - start) * max(0.0, min(1.0, progress))
        stage_start += duration
    return float(stages[-1]["end_temperature"])


def main():
    parser = argparse.ArgumentParser(description="Send natural demo telemetry.")
    parser.add_argument(
        "--profile",
        type=Path,
        default=DEFAULT_PROFILE,
        help="JSON heating profile (defaults to scripts/sensor_profile.json).",
    )
    start_group = parser.add_mutually_exclusive_group()
    start_group.add_argument(
        "--start-stage",
        type=int,
        help="Start from this stage number (1-based).",
    )
    start_group.add_argument(
        "--skip-stages",
        type=int,
        help="Skip this many stages before starting.",
    )
    args = parser.parse_args()
    profile = load_profile(args.profile)
    stages = profile.get("stages", [])
    if not stages:
        parser.error("The profile must contain at least one stage.")
    try:
        start_index = stage_start_index(args, len(stages))
    except ValueError as error:
        parser.error(str(error))
    stages = stages[start_index:]
    interval = float(profile.get("interval_seconds", 3))
    noise = float(profile.get("temperature_noise", 0.15))
    voltage = float(profile.get("voltage", 3.3))
    cooling_temperature = float(profile.get("cooling_temperature", 24.0))
    started_at = time.monotonic()
    first_stage = stages[0]
    stage_name = first_stage.get("name", f"Stage {start_index + 1}")
    print(
        f"Starting sensor profile at stage {start_index + 1}/{len(profile['stages'])}: "
        f"{stage_name} ({first_stage['start_temperature']}°C)"
    )

    while True:
        elapsed = time.monotonic() - started_at
        mash_temperature = temperature_at(elapsed, stages)
        payload = {
            "mac_address": MAC,
            "metrics": {
                "mash_temperature_sensor": round(
                    mash_temperature + random.uniform(-noise, noise), 2
                ),
                "cooling_temperature_sensor": round(
                    cooling_temperature + random.uniform(-noise, noise), 2
                ),
                "input_voltage_sensor": round(
                    voltage + random.uniform(-0.01, 0.01), 2
                ),
            },
        }
        response = requests.post(
            f"{BASE_URL}/api/v1/telemetry/",
            json=payload,
            timeout=5,
        )
        response.raise_for_status()
        print(response.json(), payload["metrics"])
        time.sleep(interval)


if __name__ == "__main__":
    main()
