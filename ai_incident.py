from __future__ import annotations

import os


def _local_summary(alert: dict) -> dict:
    return {
        "provider": "local-rule-summary",
        "summary": (
            f"{alert['severity'].upper()} incident on {alert.get('device_name', 'device')}: "
            f"{alert['message']} Recommended action: inspect the affected device, compare the "
            "reading with recent telemetry, verify sensor accuracy and connectivity, and escalate "
            "to maintenance if the condition persists."
        ),
    }


def summarize_incident(alert: dict) -> dict:
    """Use an LLM only for alert-level summaries, never for every telemetry event."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _local_summary(alert)

    try:
        from openai import OpenAI

        model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        client = OpenAI(api_key=api_key)
        prompt = (
            "You are assisting an industrial IoT operations engineer. Summarise this alert in "
            "three concise parts: likely issue, evidence, and next action. Do not claim a diagnosis; "
            "distinguish measured data from inference.\n\n"
            f"Device: {alert.get('device_name')}\n"
            f"Device type: {alert.get('device_type')}\n"
            f"Severity: {alert.get('severity')}\n"
            f"Code: {alert.get('code')}\n"
            f"Measured alert: {alert.get('message')}"
        )
        response = client.responses.create(model=model, input=prompt)
        return {"provider": f"openai:{model}", "summary": response.output_text.strip()}
    except Exception as exc:
        result = _local_summary(alert)
        result["provider"] = "local-rule-summary-after-ai-error"
        result["ai_error"] = str(exc)
        return result
