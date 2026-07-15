"""
OmniSeed Analyser — Prompt design

Each source type gets its own prompt builder rather than one generic prompt,
since "anomaly" and "relevant summary" mean different things for sensor
telemetry vs. activity data vs. document content.

PROMPT_VERSION should be bumped whenever prompt wording changes meaningfully,
and stored alongside results in the DB so you can trace which prompt logic
produced which summary.
"""

import json

PROMPT_VERSION = "v2"

RESPONSE_SCHEMA_INSTRUCTION = (
    "Respond only with valid JSON matching this schema: "
    '{"tags": string[], "summary": string, "anomaly_flag": boolean, '
    '"measurements": object, "system_fingerprint": string (optional)}. '
    "If the payload contains measurable values such as temperature, humidity, "
    "or similar, include them under 'measurements' as key/value pairs. "
    "Set 'system_fingerprint' only if you can infer a stable identifier from "
    "the supplied context; otherwise omit it. No other text before or after the JSON."
)

MAX_UPLOAD_CHARS = 4000  # local models have limited context; chunk longer docs upstream


def build_prompt(envelope: dict) -> str:
    source_type = envelope["source_type"]
    payload = envelope["raw_payload"]

    builders = {
        "iot": build_iot_prompt,
        "wearable": build_wearable_prompt,
        "upload": build_upload_prompt,
    }
    if source_type not in builders:
        raise ValueError(f"Unknown source_type: {source_type}")

    return builders[source_type](payload)


def build_iot_prompt(payload: dict) -> str:
    return f"""
The following is raw sensor telemetry (temperature, humidity, or similar).
Data: {json.dumps(payload)}

Summarize any notable readings in 1-2 sentences. Flag anomaly_flag=true if
values fall well outside a typical safe/expected range for that sensor type.
Extract any measurable values you can find from the payload into a
'measurements' object keyed by metric name (for example temperature,
humidity, pressure). Tag with relevant categories (e.g. "temperature",
"humidity", "spike", "stable").

{RESPONSE_SCHEMA_INSTRUCTION}
"""


def build_wearable_prompt(payload: dict) -> str:
    return f"""
The following is activity/health tracker data.
Data: {json.dumps(payload)}

Summarize the activity pattern in 1-2 sentences (e.g. steps, heart rate, sleep).
Flag anomaly_flag=true only for values that would concern a general health
monitoring context (e.g. unusually elevated resting heart rate).
Extract any measurable health values into a 'measurements' object when they
are present (for example steps, heart_rate, sleep_hours). Tag with relevant
categories (e.g. "activity", "sleep", "heart-rate").

{RESPONSE_SCHEMA_INSTRUCTION}
"""


def build_upload_prompt(payload: dict) -> str:
    # `payload` here is expected to be extracted text/content from the
    # uploaded file (extraction happens upstream, prior to prompt building).
    content = payload if isinstance(payload, str) else json.dumps(payload)
    truncated = content[:MAX_UPLOAD_CHARS]

    return f"""
The following is content extracted from a user-uploaded file.
Content: {truncated}

Provide a concise 2-3 sentence summary of the document's content and purpose.
Tag with relevant topical categories. Set anomaly_flag=false unless the
content itself describes an incident, error, or urgent issue. If the
content includes explicit numeric measurements or status values, include them
in a 'measurements' object; otherwise leave it empty.

{RESPONSE_SCHEMA_INSTRUCTION}
"""
