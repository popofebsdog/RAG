from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import main
from rag.anomaly import AnomalyFlagData, detect_graph_out_of_domain


class ManualNodeFlowTest(unittest.TestCase):
    @patch.object(main, "embed_query", return_value=MagicMock())
    @patch.object(main, "get_store")
    @patch.object(main.time, "time", return_value=1234.5)
    def test_same_label_nodes_created_in_same_second_have_unique_ids(
        self, _time, get_store, _embed_query
    ) -> None:
        request = main.ManualChunkRequest(
            text="First observation",
            label="Crack",
            source_doc="report.pdf",
            source_page=1,
            project_id="project-a",
        )

        first = main.create_manual_chunk(request)
        second = main.create_manual_chunk(request.model_copy(update={"text": "Second observation"}))

        self.assertNotEqual(first.chunk_id, second.chunk_id)
        self.assertEqual(get_store.return_value.upsert_manual.call_count, 2)


class QueryFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(
            main.app,
            raise_server_exceptions=False,
            headers={"Authorization": "Bearer test-rag-api-key"},
        )
        list_relations_patcher = patch.object(main, "list_relations", return_value=[])
        list_relations_patcher.start()
        self.addCleanup(list_relations_patcher.stop)
        self.store = MagicMock()
        self.store.is_ready_for_project.return_value = True
        self.store.manual_chunks.return_value = []

    def retrieval(self):
        return SimpleNamespace(results=[], max_auto_score=None, router={})

    @patch.object(main, "detect_relation_contradiction", return_value=None)
    @patch.object(main, "detect_graph_out_of_domain", return_value=None)
    @patch.object(main, "detect_out_of_domain", return_value=None)
    @patch.object(main, "retrieve")
    @patch.object(main, "get_store")
    @patch.object(main, "generate_answer", side_effect=RuntimeError("Ollama unavailable"))
    def test_llm_failure_returns_actionable_gateway_error(
        self,
        _generate_answer,
        get_store,
        retrieve,
        _detect_out_of_domain,
        _detect_graph_out_of_domain,
        _detect_contradiction,
    ) -> None:
        get_store.return_value = self.store
        retrieve.return_value = self.retrieval()

        response = self.client.post(
            "/query", json={"question": "What happened?", "project_id": "project-a"}
        )

        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn("LLM answer generation failed", response.json()["detail"])

    @patch.object(main.postgres_store, "save_query_log")
    @patch.object(main, "save_graph")
    @patch.object(main, "detect_relation_contradiction", return_value=None)
    @patch.object(main, "detect_graph_out_of_domain")
    @patch.object(main, "detect_out_of_domain", return_value=None)
    @patch.object(main, "_build_graph", return_value=main.GraphData(nodes=[], edges=[]))
    @patch.object(main, "generate_answer", return_value="The slope shows a crack.")
    @patch.object(main, "retrieve")
    @patch.object(main, "get_store")
    def test_query_returns_answer_anomaly_and_persists_log(
        self,
        get_store,
        retrieve,
        _generate_answer,
        _build_graph,
        _detect_out_of_domain,
        detect_graph_out_of_domain,
        _detect_contradiction,
        _save_graph,
        save_query_log,
    ) -> None:
        get_store.return_value = self.store
        retrieve.return_value = self.retrieval()
        detect_graph_out_of_domain.return_value = None

        response = self.client.post(
            "/query", json={"question": "Dinner recommendation?", "project_id": "project-a"}
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["answer"], "The slope shows a crack.")
        self.assertEqual(response.json()["anomalies"], [])
        save_query_log.assert_called_once()

    @patch.object(main.postgres_store, "save_query_log")
    @patch.object(main, "save_graph")
    @patch.object(main, "detect_relation_contradiction", return_value=None)
    @patch.object(main, "detect_graph_out_of_domain")
    @patch.object(main, "detect_out_of_domain", return_value=None)
    @patch.object(main, "_build_graph", return_value=main.GraphData(nodes=[], edges=[]))
    @patch.object(main, "generate_answer")
    @patch.object(main, "retrieve")
    @patch.object(main, "get_store")
    def test_out_of_domain_query_skips_llm_and_returns_safe_answer(
        self,
        get_store,
        retrieve,
        generate_answer,
        _build_graph,
        _detect_out_of_domain,
        detect_graph_out_of_domain,
        _detect_contradiction,
        _save_graph,
        _save_query_log,
    ) -> None:
        get_store.return_value = self.store
        retrieve.return_value = self.retrieval()
        detect_graph_out_of_domain.return_value = AnomalyFlagData(
            type="out_of_domain",
            message="Query is outside the knowledge base",
            details={"reason": "no_retrieved_chunks"},
        )

        response = self.client.post(
            "/query", json={"question": "Dinner recommendation?", "project_id": "project-a"}
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("不相符", response.json()["answer"])
        self.assertEqual(response.json()["anomalies"][0]["type"], "out_of_domain")
        generate_answer.assert_not_called()

    def test_query_graph_uses_configured_llm_label(self) -> None:
        store = MagicMock()
        store.docs.return_value = []
        store.get_all.return_value = ([], MagicMock())

        with patch.dict(
            main.os.environ,
            {"OLLAMA_MODEL": "gemma4:12b-it-q4_K_M"},
            clear=False,
        ):
            graph = main._build_graph("question", "answer", [], store, "project-a")

        llm_node = next(node for node in graph.nodes if node.id == "llm")
        self.assertEqual(llm_node.label, "Ollama · gemma4:12b-it-q4_K_M")

    def test_anomaly_detector_distinguishes_supported_and_unrelated_questions(self) -> None:
        retrieved = [{"label": "Slope collapse", "text": "Heavy rain caused a slope collapse."}]

        unrelated = detect_graph_out_of_domain(
            "Where should I eat dinner?", retrieved, {"a": 0.2, "b": 0.2}
        )
        supported = detect_graph_out_of_domain(
            "What caused the slope collapse?", retrieved, {"a": 0.2, "b": 0.2}
        )

        self.assertIsNotNone(unrelated)
        self.assertIsNone(supported)


if __name__ == "__main__":
    unittest.main()
