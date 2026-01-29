"""
Tests for API routes.
Uses pytest and FastAPI TestClient with fixtures.
"""
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def temp_storage_file(tmp_path):
    """Creates a temporary storage file."""
    storage_file = tmp_path / "conversations.json"
    storage_file.write_text("{}")
    return storage_file


@pytest.fixture
def test_client(temp_storage_file):
    """Creates a test client with patched storage."""
    import api.storage as storage_module
    
    # Patch the storage file path
    original_path = storage_module.CONVERSATIONS_FILE
    storage_module.CONVERSATIONS_FILE = temp_storage_file
    
    from api import create_app
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    
    yield client
    
    # Restore original
    storage_module.CONVERSATIONS_FILE = original_path


class TestConversationRoutes:
    """Tests for /api/conversations routes."""

    def test_list_conversations_empty(self, test_client):
        """GET /api/conversations returns empty list initially."""
        response = test_client.get("/api/conversations")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_conversation(self, test_client):
        """POST /api/conversations creates a new conversation."""
        response = test_client.post(
            "/api/conversations",
            json={"title": "New conversation"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "New conversation"
        assert "created_at" in data
        assert data["messages"] == []

    def test_create_conversation_default_title(self, test_client):
        """POST /api/conversations with default title."""
        response = test_client.post("/api/conversations", json={})
        assert response.status_code == 200
        assert response.json()["title"] == "New Conversation"

    def test_get_conversation(self, test_client):
        """GET /api/conversations/{id} returns the conversation."""
        # Create first
        create_resp = test_client.post("/api/conversations", json={"title": "Test"})
        assert create_resp.status_code == 200
        conv_id = create_resp.json()["id"]
        
        # Retrieve
        response = test_client.get(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        assert response.json()["id"] == conv_id

    def test_get_conversation_not_found(self, test_client):
        """GET /api/conversations/{id} returns 404 if not found."""
        response = test_client.get("/api/conversations/nonexistent")
        assert response.status_code == 404

    def test_delete_conversation(self, test_client):
        """DELETE /api/conversations/{id} deletes the conversation."""
        # Create first
        create_resp = test_client.post("/api/conversations", json={"title": "To delete"})
        assert create_resp.status_code == 200
        conv_id = create_resp.json()["id"]
        
        # Delete
        response = test_client.delete(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        
        # Verify deletion
        get_resp = test_client.get(f"/api/conversations/{conv_id}")
        assert get_resp.status_code == 404

    def test_update_conversation_title(self, test_client):
        """PATCH /api/conversations/{id} updates the title."""
        # Create first
        create_resp = test_client.post("/api/conversations", json={"title": "Original"})
        assert create_resp.status_code == 200
        conv_id = create_resp.json()["id"]
        
        # Update
        response = test_client.patch(
            f"/api/conversations/{conv_id}",
            json={"title": "Updated title"}
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated title"


class TestStatusRoute:
    """Tests for /api/status route."""

    def test_status_endpoint(self):
        """GET /api/status returns system status."""
        from api import dependencies, create_app
        
        # Save and mock state
        original_state = dependencies.state
        
        mock_state = MagicMock()
        mock_state.config = MagicMock(llm_model="qwen3:latest")
        mock_state.retriever = None
        dependencies.state = mock_state
        
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            
            response = client.get("/api/status")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
        finally:
            dependencies.state = original_state


class TestParticipantsRoute:
    """Tests for /api/participants route."""

    def test_participants_no_components(self):
        """GET /api/participants returns empty list without components."""
        from api import dependencies, create_app
        
        original_state = dependencies.state
        
        mock_state = MagicMock()
        mock_state.components = None
        mock_state.config = MagicMock()
        mock_state.retriever = None
        dependencies.state = mock_state
        
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            
            response = client.get("/api/participants")
            assert response.status_code == 200
            assert response.json() == []
        finally:
            dependencies.state = original_state

    def test_participants_with_metadata_store(self):
        """GET /api/participants returns participants from metadata store."""
        from api import dependencies, create_app
        
        original_state = dependencies.state
        
        mock_metadata_store = MagicMock()
        mock_metadata_store.get_all_participants.return_value = [
            ("Alice", 100),
            ("Bob", 50)
        ]
        
        mock_state = MagicMock()
        mock_state.components = {'metadata_store': mock_metadata_store}
        mock_state.config = MagicMock()
        mock_state.retriever = None
        dependencies.state = mock_state
        
        try:
            app = create_app()
            client = TestClient(app, raise_server_exceptions=False)
            
            response = client.get("/api/participants")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["name"] == "Alice"
            assert data[0]["count"] == 100
        finally:
            dependencies.state = original_state


if __name__ == '__main__':
    pytest.main([__file__, '-v'])