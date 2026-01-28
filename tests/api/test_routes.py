"""
Tests pour les routes API.
Utilise pytest et TestClient de FastAPI avec fixtures.
"""
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def temp_storage_file(tmp_path):
    """Crée un fichier de stockage temporaire."""
    storage_file = tmp_path / "conversations.json"
    storage_file.write_text("{}")
    return storage_file


@pytest.fixture
def test_client(temp_storage_file):
    """Crée un client de test avec storage patché."""
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
    """Tests pour les routes /api/conversations."""

    def test_list_conversations_empty(self, test_client):
        """GET /api/conversations retourne liste vide initialement."""
        response = test_client.get("/api/conversations")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_conversation(self, test_client):
        """POST /api/conversations crée une nouvelle conversation."""
        response = test_client.post(
            "/api/conversations",
            json={"title": "Nouvelle conversation"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "Nouvelle conversation"
        assert "created_at" in data
        assert data["messages"] == []

    def test_create_conversation_default_title(self, test_client):
        """POST /api/conversations avec titre par défaut."""
        response = test_client.post("/api/conversations", json={})
        assert response.status_code == 200
        assert response.json()["title"] == "Nouvelle conversation"

    def test_get_conversation(self, test_client):
        """GET /api/conversations/{id} retourne la conversation."""
        # Créer d'abord
        create_resp = test_client.post("/api/conversations", json={"title": "Test"})
        assert create_resp.status_code == 200
        conv_id = create_resp.json()["id"]
        
        # Récupérer
        response = test_client.get(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        assert response.json()["id"] == conv_id

    def test_get_conversation_not_found(self, test_client):
        """GET /api/conversations/{id} retourne 404 si non trouvée."""
        response = test_client.get("/api/conversations/nonexistent")
        assert response.status_code == 404

    def test_delete_conversation(self, test_client):
        """DELETE /api/conversations/{id} supprime la conversation."""
        # Créer d'abord
        create_resp = test_client.post("/api/conversations", json={"title": "To delete"})
        assert create_resp.status_code == 200
        conv_id = create_resp.json()["id"]
        
        # Supprimer
        response = test_client.delete(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        
        # Vérifier suppression
        get_resp = test_client.get(f"/api/conversations/{conv_id}")
        assert get_resp.status_code == 404

    def test_update_conversation_title(self, test_client):
        """PATCH /api/conversations/{id} met à jour le titre."""
        # Créer d'abord
        create_resp = test_client.post("/api/conversations", json={"title": "Original"})
        assert create_resp.status_code == 200
        conv_id = create_resp.json()["id"]
        
        # Mettre à jour
        response = test_client.patch(
            f"/api/conversations/{conv_id}",
            json={"title": "Updated title"}
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated title"


class TestStatusRoute:
    """Tests pour la route /api/status."""

    def test_status_endpoint(self):
        """GET /api/status retourne l'état du système."""
        from api import dependencies, create_app
        
        # Sauvegarde et mock de l'état
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
    """Tests pour la route /api/participants."""

    def test_participants_no_components(self):
        """GET /api/participants retourne liste vide sans composants."""
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
        """GET /api/participants retourne les participants du metadata store."""
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
