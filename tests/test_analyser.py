import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyser"))

from prompts import RESPONSE_SCHEMA_INSTRUCTION, build_iot_prompt
import worker


class AnalyserPromptAndParsingTests(unittest.TestCase):
    def test_iot_prompt_requests_structured_measurements(self) -> None:
        prompt = build_iot_prompt({"temperature": 24.5, "humidity": 44})
        self.assertIn("measurements", prompt)
        self.assertIn("system_fingerprint", prompt)
        self.assertIn("temperature", prompt)
        self.assertIn("humidity", prompt)
        self.assertIn("Respond only with valid JSON", prompt)

    def test_parse_analysis_response_extracts_measurements_and_fingerprint(self) -> None:
        raw_payload = json.dumps(
            {
                "tags": ["temperature", "stable"],
                "summary": "Temperature is within a healthy range.",
                "anomaly_flag": False,
                "measurements": {"temperature": 24.5, "humidity": 44},
            }
        )
        result = worker.parse_analysis_response(raw_payload, "fingerprint-123")
        self.assertEqual(result.measurements, {"temperature": 24.5, "humidity": 44})
        self.assertEqual(result.system_fingerprint, "fingerprint-123")


if __name__ == "__main__":
    unittest.main()
