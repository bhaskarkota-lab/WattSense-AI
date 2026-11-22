"""
Persistence Filtering & Anomaly Aggregation Service
Distinguishes legitimate short-lived appliance usage from sustained excessive consumption.

CORE METHODOLOGY:
- An isolated spike (10 minutes) represents normal appliance burst (kettle, toaster, microwave).
- A sustained run of N consecutive intervals above upper threshold indicates persistent anomaly
  (unattended heating/cooling, water heater continuous draw, baseload leakage).
- Evaluates N in {1, 2, 3, 4, 6} (10m, 20m, 30m, 40m, 60m).
"""
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

class PersistenceFilteringService:
    """Detects, aggregates, and filters candidate unusual consumption intervals."""

    @staticmethod
    def detect_and_filter(
        actual: np.ndarray,
        expected: np.ndarray,
        upper_bound: np.ndarray,
        timestamps: np.ndarray,
        min_consecutive_intervals: int = 3,
        interval_minutes: int = 10,
        unit: str = "Wh"
    ) -> Dict[str, Any]:
        """
        Executes persistence-based anomaly filtering.
        
        Parameters:
        - actual: Observed consumption values.
        - expected: Expected baseline values.
        - upper_bound: Upper threshold values.
        - timestamps: Array of timestamp objects or strings.
        - min_consecutive_intervals: Minimum consecutive periods required to trigger an alert.
        - interval_minutes: Duration of each step (e.g. 10 for UCI).
        - unit: Measurement unit (e.g. "Wh" or "kWh").
        """
        n = len(actual)
        candidate_mask = (actual > upper_bound).astype(int)

        # Identify contiguous runs of 1s in candidate_mask
        runs = []
        in_run = False
        start_idx = 0

        for i in range(n):
            if candidate_mask[i] == 1:
                if not in_run:
                    in_run = True
                    start_idx = i
            else:
                if in_run:
                    in_run = False
                    runs.append((start_idx, i - 1))
        if in_run:
            runs.append((start_idx, n - 1))

        # Filter runs by persistence threshold
        sustained_mask = np.zeros(n, dtype=int)
        events = []
        suppressed_spikes_count = 0

        for start, end in runs:
            duration_steps = end - start + 1
            if duration_steps < min_consecutive_intervals:
                suppressed_spikes_count += 1
                continue

            # This run meets the persistence requirement
            sustained_mask[start : end + 1] = 1
            run_actual = actual[start : end + 1]
            run_expected = expected[start : end + 1]
            run_upper = upper_bound[start : end + 1]
            run_excess = np.maximum(0.0, run_actual - run_upper)

            total_excess_val = float(round(np.sum(run_excess), 2))
            peak_val = float(round(np.max(run_actual), 2))
            mean_val = float(round(np.mean(run_actual), 2))
            mean_exp = float(round(np.mean(run_expected), 2))
            duration_minutes = duration_steps * interval_minutes

            # Assign severity based on duration and excess magnitude
            if duration_steps >= 6 or total_excess_val > 500.0:
                severity = "HIGH"
            elif duration_steps >= 4 or total_excess_val > 250.0:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            start_ts = str(timestamps[start])
            end_ts = str(timestamps[end])

            events.append({
                "start_index": int(start),
                "end_index": int(end),
                "start_time": start_ts,
                "end_time": end_ts,
                "consecutive_steps": int(duration_steps),
                "duration_minutes": int(duration_minutes),
                "duration_hours": round(duration_minutes / 60.0, 2),
                "peak_consumption": peak_val,
                "mean_consumption": mean_val,
                "expected_baseline": mean_exp,
                "potential_excess": total_excess_val,
                "unit": unit,
                "severity": severity
            })

        total_excess_all = float(round(sum(e["potential_excess"] for e in events), 2))
        total_duration_hours = float(round(sum(e["duration_hours"] for e in events), 2))

        return {
            "min_consecutive_intervals": min_consecutive_intervals,
            "interval_minutes": interval_minutes,
            "total_raw_candidate_intervals": int(np.sum(candidate_mask)),
            "total_candidate_runs": len(runs),
            "suppressed_isolated_spikes": suppressed_spikes_count,
            "sustained_alert_events_count": len(events),
            "total_sustained_intervals": int(np.sum(sustained_mask)),
            "total_potential_excess": total_excess_all,
            "total_duration_hours": total_duration_hours,
            "unit": unit,
            "sustained_mask": sustained_mask,
            "events": events
        }
