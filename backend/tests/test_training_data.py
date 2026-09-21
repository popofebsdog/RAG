from __future__ import annotations

import json
import unittest

from rag.training_data import build_review_sample, export_sft_jsonl


class TrainingDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pending = {
            "preview_id": "preview_123",
            "project_id": "project-a",
            "filename": "report.pdf",
            "source_sha256": "abc123",
            "model_name": "gemma4:12b-it-q4_K_M",
            "prompt_version": "knowledge-extraction-v1",
            "nodes": [
                {
                    "id": "knowledge:0",
                    "kind": "knowledge",
                    "label": "原始標籤",
                    "text": "原始內容",
                    "source_page": 2,
                    "source_doc": "report.pdf",
                    "approved": True,
                },
                {
                    "id": "knowledge:1",
                    "kind": "knowledge",
                    "label": "錯誤節點",
                    "text": "不應入庫",
                    "source_page": 3,
                    "source_doc": "report.pdf",
                    "approved": True,
                },
            ],
            "relations": [
                {
                    "id": "relation:0",
                    "source_node_id": "knowledge:0",
                    "target_node_id": "knowledge:1",
                    "label": "導致",
                    "weight": 0.4,
                    "approved": True,
                }
            ],
        }

    def test_build_review_sample_preserves_original_and_reviewed_differences(self) -> None:
        reviewed_nodes = [
            {
                **self.pending["nodes"][0],
                "label": "修正標籤",
                "text": "專業人員修正內容",
            },
            {**self.pending["nodes"][1], "approved": False},
        ]
        reviewed_relations = [
            {**self.pending["relations"][0], "weight": 0.9, "approved": False}
        ]

        sample = build_review_sample(
            self.pending,
            reviewed_nodes,
            reviewed_relations,
            reviewer_id="engineer-7",
            review_notes="現地調查確認",
            training_eligible=True,
        )

        self.assertEqual(sample["original"]["nodes"], self.pending["nodes"])
        self.assertEqual(sample["reviewed"]["nodes"], reviewed_nodes)
        self.assertEqual(sample["reviewer_id"], "engineer-7")
        self.assertEqual(sample["review_notes"], "現地調查確認")
        self.assertTrue(sample["training_eligible"])
        self.assertEqual(sample["changes"]["nodes"][0]["status"], "modified")
        self.assertEqual(sample["changes"]["nodes"][1]["status"], "rejected")
        self.assertEqual(sample["changes"]["relations"][0]["status"], "rejected")
        self.assertEqual(sample["changes"]["relations"][0]["fields"]["weight"], {"before": 0.4, "after": 0.9})

    def test_dataset_split_is_stable_for_the_same_source(self) -> None:
        splits = {
            build_review_sample(
                {**self.pending, "preview_id": f"preview_reuploaded_{index}"},
                self.pending["nodes"],
                self.pending["relations"],
            )["dataset_split"]
            for index in range(30)
        }

        self.assertEqual(len(splits), 1)
        self.assertTrue(splits <= {"train", "validation", "test"})

    def test_export_sft_jsonl_excludes_ineligible_samples_and_keeps_provenance(self) -> None:
        eligible = build_review_sample(
            self.pending,
            self.pending["nodes"],
            self.pending["relations"],
            reviewer_id="engineer-7",
            training_eligible=True,
        )
        ineligible = build_review_sample(
            {**self.pending, "preview_id": "preview_456"},
            self.pending["nodes"],
            self.pending["relations"],
            training_eligible=False,
        )

        payload = export_sft_jsonl([eligible, ineligible])
        rows = [json.loads(line) for line in payload.splitlines() if line]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["messages"][0]["role"], "system")
        self.assertEqual(rows[0]["messages"][-1]["role"], "assistant")
        self.assertEqual(rows[0]["metadata"]["source_sha256"], "abc123")
        self.assertEqual(rows[0]["metadata"]["model_name"], "gemma4:12b-it-q4_K_M")
        self.assertEqual(rows[0]["metadata"]["reviewer_id"], "engineer-7")


if __name__ == "__main__":
    unittest.main()
