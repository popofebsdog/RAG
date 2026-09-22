from __future__ import annotations

import unittest
import json
from unittest.mock import Mock, patch

import main
from rag.training_data import build_relation_review_sample, export_sft_jsonl


def relation(weight: float = 0.6) -> dict:
    return {
        "id": "rel-1",
        "from_chunk_id": "node-a",
        "to_chunk_id": "node-b",
        "label": "導致",
        "weight": weight,
        "project_id": "project-a",
        "created_at": 123,
        "vectorized": True,
    }


class RelationTrainingDataTest(unittest.TestCase):
    @patch.object(main, "add_relation")
    @patch.object(main, "list_relations", return_value=[])
    def test_missing_reviewer_is_rejected_before_create_mutation(self, _list, add) -> None:
        request = main.RelationRequest(
            from_chunk_id="node-a",
            to_chunk_id="node-b",
            label="導致",
            project_id="project-a",
            training_eligible=True,
        )

        with self.assertRaises(main.HTTPException) as raised:
            main.create_relation(request)

        self.assertEqual(raised.exception.status_code, 422)
        add.assert_not_called()

    def test_create_update_and_delete_have_training_semantics(self) -> None:
        created = build_relation_review_sample(
            "create", None, relation(), project_id="project-a", reviewer_id="engineer-7"
        )
        updated = build_relation_review_sample(
            "update", relation(0.6), relation(0.9), project_id="project-a", reviewer_id="engineer-7"
        )
        deleted = build_relation_review_sample(
            "delete", relation(), None, project_id="project-a", reviewer_id="engineer-7"
        )

        self.assertEqual(created["changes"]["relations"][0]["status"], "added")
        self.assertEqual(updated["changes"]["relations"][0]["status"], "modified")
        self.assertEqual(
            updated["changes"]["relations"][0]["fields"]["weight"],
            {"before": 0.6, "after": 0.9},
        )
        self.assertEqual(deleted["changes"]["relations"][0]["status"], "rejected")
        self.assertEqual(deleted["action"], "delete")

        exported = json.loads(export_sft_jsonl([deleted]).strip())
        self.assertEqual(exported["metadata"]["task_type"], "relation_review")
        self.assertEqual(exported["metadata"]["action"], "delete")

    @patch.object(main, "_save_relation_training_event")
    @patch.object(main, "_upsert_relation_vector")
    @patch.object(main, "add_relation")
    @patch.object(main, "list_relations", return_value=[])
    def test_create_relation_records_training_event(self, _list, add, _vector, save_event) -> None:
        add.return_value = relation()
        request = main.RelationRequest(
            from_chunk_id="node-a",
            to_chunk_id="node-b",
            label="導致",
            weight=0.6,
            project_id="project-a",
            reviewer_id="engineer-7",
            review_notes="現勘確認",
        )

        main.create_relation(request)

        save_event.assert_called_once_with("create", None, relation(), request)

    @patch.object(main, "_save_relation_training_event")
    @patch.object(main, "_upsert_relation_vector")
    @patch.object(main, "get_store")
    @patch.object(main, "update_relation_weight", return_value=True)
    @patch.object(main, "list_relations")
    def test_weight_update_records_before_and_after(
        self, list_items, _update, _store, upsert_vector, save_event
    ) -> None:
        before = relation(0.6)
        after = relation(0.9)
        list_items.side_effect = [[before], [after]]
        body = main.RelationWeightUpdate(
            weight=0.9,
            reviewer_id="engineer-7",
            review_notes="提高因果可信度",
        )

        main.update_relation_weight_endpoint("rel-1", body, project_id="project-a")

        upsert_vector.assert_called_once_with(after)
        save_event.assert_called_once_with("update", before, after, body, project_id="project-a")

    @patch.object(main, "_save_relation_training_event")
    @patch.object(main, "get_store")
    @patch.object(main, "delete_relation", return_value=True)
    @patch.object(main, "list_relations")
    def test_delete_relation_records_rejected_relation(self, list_items, _delete, _store, save_event) -> None:
        before = relation()
        list_items.return_value = [before]

        main.remove_relation_endpoint(
            "rel-1",
            project_id="project-a",
            reviewer_id="engineer-7",
            review_notes="關係方向錯誤",
            training_eligible=True,
        )

        save_event.assert_called_once_with(
            "delete",
            before,
            None,
            None,
            project_id="project-a",
            reviewer_id="engineer-7",
            review_notes="關係方向錯誤",
            training_eligible=True,
        )


if __name__ == "__main__":
    unittest.main()
