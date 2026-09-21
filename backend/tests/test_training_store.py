from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import patch

from rag import postgres_store


class FakeResult:
    def __init__(self, rows=None):
        self.rows = rows or []

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows=None):
        self.calls = []
        self.rows = rows or []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return FakeResult(self.rows)


class TrainingStoreTest(unittest.TestCase):
    def test_init_schema_creates_training_review_samples(self) -> None:
        conn = FakeConnection()

        @contextmanager
        def fake_connect():
            yield conn

        with patch.object(postgres_store, "is_enabled", return_value=True), \
             patch.object(postgres_store, "connect", fake_connect):
            postgres_store.init_schema()

        schema_sql = conn.calls[0][0]
        self.assertIn("CREATE TABLE IF NOT EXISTS training_review_samples", schema_sql)
        self.assertIn("sample JSONB NOT NULL", schema_sql)
        self.assertIn("training_eligible BOOLEAN NOT NULL", schema_sql)
        self.assertIn("dataset_split TEXT NOT NULL", schema_sql)

    def test_save_and_list_training_review_samples(self) -> None:
        sample = {
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
        }
        conn = FakeConnection(rows=[{"sample": sample}])

        @contextmanager
        def fake_connect():
            yield conn

        with patch.object(postgres_store, "is_enabled", return_value=True), \
             patch.object(postgres_store, "ensure_project"), \
             patch.object(postgres_store, "connect", fake_connect), \
             patch.object(postgres_store, "Jsonb", side_effect=lambda value: value):
            postgres_store.save_training_review_sample(sample)
            rows = postgres_store.list_training_review_samples("project-a", dataset_split="train")

        insert_sql, insert_params = conn.calls[0]
        self.assertIn("INSERT INTO training_review_samples", insert_sql)
        self.assertEqual(insert_params[-1], sample)
        self.assertEqual(rows, [sample])
        self.assertIn("dataset_split = %s", conn.calls[1][0])


if __name__ == "__main__":
    unittest.main()
