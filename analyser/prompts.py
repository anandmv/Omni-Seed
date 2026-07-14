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

PROMPT_VERSION = "v1"

RESPONSE_SCHEMA_INSTRUCTION = (
    "Respond only with valid JSON matching this schema: "
    '{"tags": string[], "summary": string, "anomaly_flag": boolean}. '
    "No other text before or after the JSON."
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
Tag with relevant categories (e.g. "temperature", "humidity", "spike", "stable").

{RESPONSE_SCHEMA_INSTRUCTION}
"""


def build_wearable_prompt(payload: dict) -> str:
    return f"""
The following is activity/health tracker data.
Data: {json.dumps(payload)}

Summarize the activity pattern in 1-2 sentences (e.g. steps, heart rate, sleep).
Flag anomaly_flag=true only for values that would concern a general health
monitoring context (e.g. unusually elevated resting heart rate).
Tag with relevant categories (e.g. "activity", "sleep", "heart-rate").

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
content itself describes an incident, error, or urgent issue.

{RESPONSE_SCHEMA_INSTRUCTION}
"""
