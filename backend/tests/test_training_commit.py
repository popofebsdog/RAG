from __future__ import annotations

import unittest
from unittest.mock import patch

import main


class TrainingCommitTest(unittest.TestCase):
    def test_training_eligible_review_requires_reviewer_id(self) -> None:
        request = main.IngestCommitRequest(
            preview_id="preview-1",
            project_id="project-a",
            filename="report.pdf",
            nodes=[],
            training_eligible=True,
        )

        with self.assertRaises(main.HTTPException) as raised:
            main._save_training_review_from_commit({}, request)

        self.assertEqual(raised.exception.status_code, 422)

    @patch.object(main.postgres_store, "save_training_review_sample")
    @patch.object(main, "build_review_sample")
    def test_commit_metadata_is_used_to_persist_review_sample(self, build_sample, save_sample) -> None:
        pending = {
            "preview_id": "preview-1",
            "project_id": "project-a",
            "filename": "report.pdf",
            "nodes": [{"id": "knowledge:0", "approved": True}],
            "relations": [],
        }
        request = main.IngestCommitRequest(
            preview_id="preview-1",
            project_id="project-a",
            filename="report.pdf",
            nodes=[
                main.CandidateNode(
                    id="knowledge:0",
                    label="修正節點",
                    text="修正內容",
                    source_doc="report.pdf",
                )
            ],
            reviewer_id="engineer-7",
            review_notes="完成現勘確認",
            training_eligible=True,
        )
        built = {"sample_id": "sample-1"}
        build_sample.return_value = built

        result = main._save_training_review_from_commit(pending, request)

        self.assertEqual(result, built)
        build_sample.assert_called_once_with(
            pending,
            [request.nodes[0].model_dump()],
            [],
            reviewer_id="engineer-7",
            review_notes="完成現勘確認",
            training_eligible=True,
        )
        save_sample.assert_called_once_with(built)


if __name__ == "__main__":
    unittest.main()
