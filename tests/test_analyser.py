import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analyser"))

from prompts import RESPONSE_SCHEMA_INSTRUCTION, build_iot_prompt, build_prompt, build_wearable_prompt
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

    # ------------------------------------------------------------------
    # Additional tests
    # ------------------------------------------------------------------

    def test_parse_valid_minimal_response(self) -> None:
        """Only required fields present — optional fields default to None."""
        raw = json.dumps(
            {
                "tags": ["stable"],
                "summary": "All readings normal.",
                "anomaly_flag": False,
            }
        )
        result = worker.parse_analysis_response(raw, None)
        self.assertIsNone(result.measurements)
        self.assertIsNone(result.system_fingerprint)

    def test_parse_anomaly_flag_true(self) -> None:
        """anomaly_flag=true in payload should come through as Python True."""
        raw = json.dumps(
            {
                "tags": ["spike"],
                "summary": "Temperature spike detected.",
                "anomaly_flag": True,
            }
        )
        result = worker.parse_analysis_response(raw, None)
        self.assertTrue(result.anomaly_flag)

    def test_parse_invalid_json_raises(self) -> None:
        """Non-JSON input must raise ValueError."""
        with self.assertRaises(ValueError):
            worker.parse_analysis_response("not json", None)

    def test_parse_non_object_json_raises(self) -> None:
        """A JSON array (not object) must raise ValueError."""
        with self.assertRaises(ValueError):
            worker.parse_analysis_response('["list"]', None)

    def test_parse_measurements_must_be_object(self) -> None:
        """measurements present but not a dict must raise ValueError."""
        raw = json.dumps(
            {
                "tags": [],
                "summary": "x",
                "anomaly_flag": False,
                "measurements": "bad",
            }
        )
        with self.assertRaises(ValueError):
            worker.parse_analysis_response(raw, None)

    def test_wearable_prompt_contains_expected_keys(self) -> None:
        """Wearable prompt should reference activity/health metric terminology."""
        envelope = {
            "source_type": "wearable",
            "raw_payload": {"steps": 8000, "heart_rate": 72},
        }
        prompt = build_prompt(envelope)
        self.assertTrue(
            any(kw in prompt for kw in ("steps", "heart_rate", "wearable", "activity", "heart")),
            msg=f"Expected wearable keywords in prompt, got:\n{prompt}",
        )

    def test_upload_prompt_contains_expected_keys(self) -> None:
        """Upload prompt should reference upload/file content terminology."""
        envelope = {
            "source_type": "upload",
            "raw_payload": "Annual report content goes here.",
        }
        prompt = build_prompt(envelope)
        self.assertTrue(
            any(kw in prompt for kw in ("upload", "file", "document", "content")),
            msg=f"Expected upload keywords in prompt, got:\n{prompt}",
        )


if __name__ == "__main__":
    unittest.main()
