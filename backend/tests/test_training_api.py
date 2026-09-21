from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class TrainingApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(
            main.app,
            headers={"Authorization": "Bearer test-rag-api-key"},
        )
        self.sample = {
            "sample_id": "sample-1",
            "project_id": "project-a",
            "preview_id": "preview-1",
            "filename": "report.pdf",
            "source_sha256": "abc123",
            "model_name": "gemma4:12b-it-q4_K_M",
            "prompt_version": "knowledge-extraction-v1",
            "reviewer_id": "engineer-7",
            "training_eligible": True,
            "dataset_split": "train",
            "original": {"nodes": [], "relations": []},
            "reviewed": {"nodes": [], "relations": []},
        }

    @patch.object(main.postgres_store, "list_training_review_samples")
    def test_list_training_samples(self, list_samples) -> None:
        list_samples.return_value = [self.sample]

        response = self.client.get(
            "/training/reviews",
            params={"project_id": "project-a", "dataset_split": "train"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [self.sample])
        list_samples.assert_called_once_with("project-a", dataset_split="train", eligible_only=False)

    @patch.object(main.postgres_store, "list_training_review_samples")
    def test_export_training_samples_as_downloadable_jsonl(self, list_samples) -> None:
        list_samples.return_value = [self.sample]

        response = self.client.get(
            "/training/export",
            params={"project_id": "project-a", "dataset_split": "train"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/x-ndjson")
        self.assertIn("attachment", response.headers["content-disposition"])
        row = json.loads(response.text.strip())
        self.assertEqual(row["metadata"]["sample_id"], "sample-1")
        list_samples.assert_called_once_with("project-a", dataset_split="train", eligible_only=True)


if __name__ == "__main__":
    unittest.main()
