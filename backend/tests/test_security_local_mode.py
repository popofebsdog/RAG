from __future__ import annotations

import io
import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import main
from rag import llm
from rag import loader


API_KEY = "test-rag-api-key"
AUTH_HEADERS = {"Authorization": f"Bearer {API_KEY}"}


class SingleUserAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main.app)

    def test_health_is_public(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)

    @patch.object(main.postgres_store, "list_projects", return_value=[])
    def test_protected_api_rejects_missing_credentials(self, _list_projects) -> None:
        response = self.client.get("/projects")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("www-authenticate"), "Bearer")

    @patch.object(main.postgres_store, "list_projects", return_value=[])
    def test_protected_api_accepts_configured_bearer_token(self, _list_projects) -> None:
        response = self.client.get("/projects", headers=AUTH_HEADERS)

        self.assertEqual(response.status_code, 200)

    @patch.object(main.postgres_store, "list_projects", return_value=[])
    def test_intranet_mode_accepts_api_requests_without_credentials(self, _list_projects) -> None:
        with patch.dict(os.environ, {"RAG_AUTH_ENABLED": "0"}, clear=False):
            response = self.client.get("/api/projects")

        self.assertEqual(response.status_code, 200)

    def test_missing_server_key_fails_closed(self) -> None:
        with patch.dict(os.environ, {"RAG_API_KEY": ""}, clear=False):
            response = self.client.get("/projects", headers=AUTH_HEADERS)

        self.assertEqual(response.status_code, 503)

    def test_session_endpoint_sets_http_only_cookie(self) -> None:
        response = self.client.post("/auth/session", headers=AUTH_HEADERS)

        self.assertEqual(response.status_code, 204)
        cookie = response.headers.get("set-cookie", "")
        self.assertIn("rag_session=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=strict", cookie)


class LocalGemmaModelTest(unittest.TestCase):
    @patch.object(llm.httpx, "post")
    def test_answer_generation_uses_local_gemma4(self, post) -> None:
        post.return_value.json.return_value = {"message": {"content": "ok"}}

        with patch.dict(
            os.environ,
            {"OLLAMA_URL": "http://ollama.local:11434", "OLLAMA_MODEL": "gemma4:12b-it-q4_K_M"},
            clear=False,
        ):
            result = llm._ollama_chat("system", "question")

        self.assertEqual(result, "ok")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://ollama.local:11434/api/chat")
        self.assertEqual(kwargs["json"]["model"], "gemma4:12b-it-q4_K_M")

    @patch("httpx.post")
    def test_pdf_vision_uses_local_gemma4_with_images(self, post) -> None:
        post.return_value.json.return_value = {"message": {"content": "## Page 1\n- result"}}

        with patch.dict(
            os.environ,
            {"OLLAMA_URL": "http://ollama.local:11434", "OLLAMA_MODEL": "gemma4:12b-it-q4_K_M"},
            clear=False,
        ):
            result = loader._vlm_extract_page(["image-one", "image-two"], 1)

        self.assertIn("Page 1", result)
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://ollama.local:11434/api/chat")
        self.assertEqual(kwargs["json"]["model"], "gemma4:12b-it-q4_K_M")
        self.assertFalse(kwargs["json"]["think"])
        self.assertEqual(kwargs["json"]["messages"][0]["images"], ["image-one", "image-two"])

    @patch("httpx.post")
    def test_pdf_vision_can_enable_model_thinking(self, post) -> None:
        post.return_value.json.return_value = {"message": {"content": "## Page 1\n- result"}}

        with patch.dict(os.environ, {"OLLAMA_VLM_THINK": "1"}, clear=False):
            loader._vlm_extract_page(["image-one"], 1)

        self.assertTrue(post.call_args.kwargs["json"]["think"])

    @patch.object(main.httpx, "post")
    def test_selection_vision_uses_local_gemma4(self, post) -> None:
        post.return_value.json.return_value = {
            "message": {
                "content": '{"label":"crack","description":"visible crack","evidence_type":"photo"}'
            }
        }

        with patch.dict(
            os.environ,
            {"OLLAMA_URL": "http://ollama.local:11434", "OLLAMA_MODEL": "gemma4:12b-it-q4_K_M"},
            clear=False,
        ):
            label, description, evidence_type = main._describe_vlm_selection(
                "data:image/png;base64,aW1hZ2U=", "report.pdf", 2
            )

        self.assertEqual((label, description, evidence_type), ("crack", "visible crack", "photo"))
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://ollama.local:11434/api/chat")
        self.assertEqual(kwargs["json"]["model"], "gemma4:12b-it-q4_K_M")
        self.assertEqual(kwargs["json"]["messages"][0]["images"], ["aW1hZ2U="])

    @patch.object(main, "get_image_store")
    @patch.object(main, "embed_query")
    @patch.object(
        main,
        "_describe_vlm_selection",
        return_value=("crack", "visible crack on the slope", "photo"),
    )
    def test_image_chunk_uses_gemma_description_and_local_text_embedding(
        self, describe_selection, embed_query, get_image_store
    ) -> None:
        embedding = MagicMock()
        embed_query.return_value = embedding
        request = main.ImageChunkRequest(
            label="Slope crack",
            source_doc="report.pdf",
            source_page=3,
            image_index=1,
            data_b64="aW1hZ2U=",
            project_id="project-a",
        )

        result = main.create_image_chunk(request)

        self.assertEqual(result.label, "Slope crack")
        describe_selection.assert_called_once_with("aW1hZ2U=", "report.pdf", 3)
        embed_query.assert_called_once_with("Slope crack\nvisible crack on the slope")
        self.assertIs(get_image_store.return_value.upsert_image.call_args.kwargs["embedding"], embedding)


class UploadSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main.app)

    def test_rejects_pdf_larger_than_configured_limit(self) -> None:
        with patch.dict(os.environ, {"PDF_MAX_UPLOAD_BYTES": "8"}, clear=False):
            response = self.client.post(
                "/ingest",
                headers=AUTH_HEADERS,
                files={"file": ("large.pdf", b"%PDF-1234", "application/pdf")},
            )

        self.assertEqual(response.status_code, 413)

    def test_rejects_file_with_pdf_extension_but_invalid_signature(self) -> None:
        response = self.client.post(
            "/ingest",
            headers=AUTH_HEADERS,
            files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("signature", response.json()["detail"].lower())

    def test_rejects_pdf_over_page_limit_before_loader_runs(self) -> None:
        import fitz

        document = fitz.open()
        document.new_page()
        document.new_page()
        pdf_bytes = document.tobytes()
        document.close()

        with (
            patch.dict(os.environ, {"PDF_MAX_PAGES": "1"}, clear=False),
            patch.object(main, "get_loader") as get_loader,
        ):
            response = self.client.post(
                "/ingest",
                headers=AUTH_HEADERS,
                files={"file": ("two-pages.pdf", pdf_bytes, "application/pdf")},
            )

        self.assertEqual(response.status_code, 413)
        get_loader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
