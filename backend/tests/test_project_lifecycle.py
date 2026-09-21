from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import main
from rag.loader import PageContent


class ProjectLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(
            main.app,
            headers={"Authorization": "Bearer test-rag-api-key"},
        )

    @patch.object(main.postgres_store, "remove_document")
    @patch.object(main, "remove_pages")
    @patch.object(main, "_remove_doc_graph_artifacts")
    @patch.object(main, "list_page_docs", return_value=["report.pdf"])
    @patch.object(main, "get_store")
    def test_remove_file_deletes_persisted_document_record(
        self, get_store, _list_page_docs, _remove_artifacts, _remove_pages, remove_document
    ) -> None:
        get_store.return_value.docs.return_value = []

        response = self.client.delete(
            "/project/files/report.pdf", params={"project_id": "project-a"}
        )

        self.assertEqual(response.status_code, 200)
        remove_document.assert_called_once_with("project-a", "report.pdf")

    @patch.object(main.postgres_store, "clear_project")
    @patch.object(main, "clear_relations")
    @patch.object(main, "clear_graphs")
    @patch.object(main, "clear_images")
    @patch.object(main, "clear_ocr")
    @patch.object(main, "clear_sources")
    @patch.object(main, "clear_markdown")
    @patch.object(main, "clear_pages")
    @patch.object(main, "list_relations", return_value=[])
    @patch.object(main, "get_image_store")
    @patch.object(main, "get_store")
    def test_clear_project_deletes_persisted_document_records(
        self,
        _get_store,
        _get_image_store,
        _list_relations,
        _clear_pages,
        _clear_markdown,
        _clear_sources,
        _clear_ocr,
        _clear_images,
        _clear_graphs,
        _clear_relations,
        clear_project,
    ) -> None:
        response = self.client.delete("/project/clear", params={"project_id": "project-a"})

        self.assertEqual(response.status_code, 200)
        clear_project.assert_called_once_with("project-a")

    @patch.object(main.postgres_store, "delete_project", create=True)
    @patch.object(main, "project_clear")
    def test_delete_project_clears_assets_then_deletes_project_record(
        self, project_clear, delete_project
    ) -> None:
        project_clear.return_value = {"status": "cleared"}

        response = self.client.delete("/projects/project-a")

        self.assertEqual(response.status_code, 200)
        project_clear.assert_called_once_with("project-a")
        delete_project.assert_called_once_with("project-a")

    @patch.object(main, "_remove_pending_ingest")
    @patch.object(main, "remove_images")
    @patch.object(main, "remove_ocr")
    @patch.object(main, "remove_source")
    @patch.object(main, "remove_markdown")
    @patch.object(main, "remove_pages")
    @patch.object(main, "_load_pending_ingest")
    def test_discard_preview_removes_new_uncommitted_file(
        self,
        load_pending,
        remove_pages,
        remove_markdown,
        remove_source,
        remove_ocr,
        remove_images,
        remove_pending,
    ) -> None:
        load_pending.return_value = {
            "filename": "new-report.pdf",
            "was_existing": False,
        }

        response = self.client.delete(
            "/ingest/preview/preview-1", params={"project_id": "project-a"}
        )

        self.assertEqual(response.status_code, 200)
        remove_pages.assert_called_once_with("new-report.pdf", project_id="project-a")
        remove_markdown.assert_called_once_with("new-report.pdf", project_id="project-a")
        remove_source.assert_called_once_with("new-report.pdf", project_id="project-a")
        remove_ocr.assert_called_once_with("new-report.pdf", project_id="project-a")
        remove_images.assert_called_once_with("new-report.pdf", project_id="project-a")
        remove_pending.assert_called_once_with("project-a", "preview-1")

    @patch.object(main, "_remove_pending_ingest")
    @patch.object(main, "remove_pages")
    @patch.object(main, "_load_pending_ingest")
    def test_discard_preview_preserves_existing_file(
        self, load_pending, remove_pages, remove_pending
    ) -> None:
        load_pending.return_value = {
            "filename": "existing-report.pdf",
            "was_existing": True,
        }

        response = self.client.delete(
            "/ingest/preview/preview-2", params={"project_id": "project-a"}
        )

        self.assertEqual(response.status_code, 200)
        remove_pages.assert_not_called()
        remove_pending.assert_called_once_with("project-a", "preview-2")

    @patch.object(main, "_save_pending_ingest")
    @patch.object(main, "_save_pending_ingest_source", create=True)
    @patch.object(main, "_build_ingest_candidates", return_value=([], []))
    @patch.object(main, "extract_knowledge_graph")
    @patch.object(main, "store_images")
    @patch.object(main, "store_markdown")
    @patch.object(main, "store_pages")
    @patch.object(main, "store_pdf")
    @patch.object(main, "list_page_docs", return_value=[])
    @patch.object(main.postgres_store, "list_documents", return_value=[])
    @patch.object(main, "get_store")
    @patch.object(main, "get_loader")
    def test_preview_stages_source_without_writing_project_files(
        self,
        get_loader,
        get_store,
        _list_documents,
        _list_page_docs,
        store_pdf,
        store_pages,
        store_markdown,
        store_images,
        _extract_graph,
        _build_candidates,
        save_source,
        save_pending,
    ) -> None:
        import fitz

        get_loader.return_value.load.return_value = [PageContent(page_num=1, text="Inspection note")]
        get_store.return_value.docs.return_value = []
        document = fitz.open()
        document.new_page()
        pdf_bytes = document.tobytes()
        document.close()

        response = self.client.post(
            "/ingest/preview",
            files={"file": ("report.pdf", pdf_bytes, "application/pdf")},
            data={"project_id": "project-a", "loader_type": "pymupdf"},
        )

        self.assertEqual(response.status_code, 200)
        store_pdf.assert_not_called()
        store_pages.assert_not_called()
        store_markdown.assert_not_called()
        store_images.assert_not_called()
        save_source.assert_called_once()
        pending = save_pending.call_args.args[2]
        self.assertEqual(pending["pages"][0]["text"], "Inspection note ^p1-inspection-note-1")


if __name__ == "__main__":
    unittest.main()
