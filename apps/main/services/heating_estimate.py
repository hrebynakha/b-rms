import math


def heating_estimate(readings, target, *, active, available, since=None):
    """Extrapolate a recent measured slope; no assumed heater power or water model."""
    result = {"eta_seconds": None, "heating_rate_c_per_min": None,
              "estimate_intervals": 0, "eta_status": "inactive"}
    if not active or not available:
        return result
    if readings and readings[0].value >= target:
        return {**result, "eta_seconds": 0, "eta_status": "reached"}
    window = []
    for reading in readings:
        if since and reading.created_at < since:
            break
        if not math.isfinite(reading.value):
            break
        if window:
            gap = (window[-1].created_at - reading.created_at).total_seconds()
            if gap > 10:
                break
            if gap <= 0:
                continue
        window.append(reading)
    result["estimate_intervals"] = max(0, len(window) - 1)
    result["eta_status"] = "collecting"
    if len(window) < 6:
        return result
    origin = window[-1].created_at
    times = [(reading.created_at - origin).total_seconds() for reading in window]
    average_time = sum(times) / len(times)
    average_temperature = sum(reading.value for reading in window) / len(window)
    variance = sum((time - average_time) ** 2 for time in times)
    if variance == 0:
        return result
    slope = sum((time - average_time) * (reading.value - average_temperature)
                for time, reading in zip(times, window)) / variance
    result["heating_rate_c_per_min"] = round(slope * 60, 3)
    if slope <= .001 or window[0].value - window[-1].value <= .05:
        result["eta_status"] = "not_warming"
        return result
    seconds = (target - window[0].value) / slope
    if not math.isfinite(seconds) or seconds > 86400:
        result["eta_status"] = "unstable"
        return result
    result.update(eta_seconds=max(1, round(seconds)), eta_status="estimated")
    return result
