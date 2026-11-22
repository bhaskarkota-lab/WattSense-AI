"""
Customer Findings Service
Transforms internal detection results into clear, supportive, customer-friendly insights.

STRICT SANITIZATION RULES:
- Never expose anomaly scores, internal model names, or training metrics.
- Never expose theft labels or dataset names.
- Never claim an appliance is broken without verified component sub-metering.
- Frame excess usage as 'potential excess usage' rather than proven waste.
"""
from typing import List, Dict, Any, Optional

class CustomerFindingsService:
    """Generates customer-ready consumption findings and narrative summaries."""

    @staticmethod
    def generate_findings(
        events: List[Dict[str, Any]],
        unit: str = "kWh",
        total_excess: float = 0.0,
        period_description: str = "the analysed period"
    ) -> Dict[str, Any]:
        """
        Translates raw detected events into clear, actionable customer findings.
        """
        if not events:
            return {
                "headline": "Electricity Consumption Within Normal Expected Range",
                "summary": (
                    f"During {period_description}, your electricity consumption closely followed your typical "
                    "historical baseline. No sustained periods of unusual or unnecessary usage were detected."
                ),
                "key_findings": [
                    "Your daily and overnight baseload remained stable and consistent.",
                    "No prolonged consumption surges occurred during low-demand hours.",
                    "Isolated, short-term usage spikes aligned with normal household appliance activity."
                ],
                "alert_level": "NORMAL",
                "events_count": 0,
                "total_potential_excess": 0.0,
                "unit": unit
            }

        # Analyze timing of events
        overnight_events = [e for e in events if "00:" in e.get("start_time", "") or "01:" in e.get("start_time", "") or "02:" in e.get("start_time", "") or "03:" in e.get("start_time", "") or "04:" in e.get("start_time", "")]
        extended_events = [e for e in events if e.get("duration_hours", 0) >= 1.5]

        findings_list = []
        if overnight_events:
            findings_list.append(
                f"Identified {len(overnight_events)} period(s) where electricity consumption remained elevated overnight "
                "when the household is typically at rest. This pattern often indicates unmonitored baseline loads or continuous heating/cooling."
            )

        if extended_events:
            findings_list.append(
                f"Observed {len(extended_events)} prolonged consumption period(s) lasting over 1.5 hours above your expected usage range."
            )

        findings_list.append(
            f"Across {period_description}, approximately {total_excess:.2f} {unit} of potential excess consumption "
            "was identified across sustained unusual periods."
        )

        # Build customer-friendly narrative events
        friendly_events = []
        for idx, ev in enumerate(events, 1):
            dur_mins = ev.get("duration_minutes", int(ev.get("duration_hours", 1) * 60))
            dur_hrs = ev.get("duration_hours", round(dur_mins / 60.0, 2))
            dur_text = f"{dur_mins} minutes" if dur_mins < 60 else f"{dur_hrs} hours"
            sev = ev.get("severity", "MEDIUM")
            pot_excess = ev.get("potential_excess", ev.get("potential_excess_wh", ev.get("potential_excess_kwh", 0.0)))
            mean_c = ev.get("mean_consumption", ev.get("actual_peak", 0.0))
            peak_c = ev.get("peak_consumption", ev.get("actual_peak", 0.0))
            exp_b = ev.get("expected_baseline", ev.get("expected_avg", 0.0))
            start_t = ev.get("start_time", "N/A")
            end_t = ev.get("end_time", "N/A")

            friendly_events.append({
                "event_id": idx,
                "time_window": f"{start_t} to {end_t}",
                "duration": dur_text,
                "severity": sev,
                "potential_excess": f"{pot_excess:.2f} {unit}",
                "description": (
                    f"Usage averaged {mean_c:.1f} {unit} (peaking at {peak_c:.1f} {unit}) "
                    f"compared to your expected baseline of {exp_b:.1f} {unit}. "
                    f"This sustained pattern lasted {dur_text}."
                )
            })

        return {
            "headline": f"Potential Unnecessary Consumption Identified ({len(events)} Sustained Period{'s' if len(events) > 1 else ''})",
            "summary": (
                f"We identified {len(events)} period(s) during {period_description} where your electricity usage "
                f"stayed consistently higher than usual, totaling an estimated {total_excess:.2f} {unit} in potential excess consumption."
            ),
            "key_findings": findings_list,
            "alert_level": "ELEVATED" if any(e["severity"] == "HIGH" for e in events) else "MODERATE",
            "events_count": len(events),
            "total_potential_excess": round(total_excess, 2),
            "unit": unit,
            "detailed_events": friendly_events
        }
