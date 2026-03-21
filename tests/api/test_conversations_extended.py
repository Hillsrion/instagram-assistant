"""
Tests for extended conversation routes (Delete All, Export).
"""
import pytest
from fastapi.testclient import TestClient
from api.storage import CONVERSATIONS_FILE
import api.storage as storage_module
from api import create_app

@pytest.fixture
def temp_storage_file(tmp_path):
    storage_file = tmp_path / "conversations_test.json"
    storage_file.write_text("{}")
    return storage_file

@pytest.fixture
def test_client(temp_storage_file):
    original_path = storage_module.CONVERSATIONS_FILE
    storage_module.CONVERSATIONS_FILE = temp_storage_file
    
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    
    yield client
    
    storage_module.CONVERSATIONS_FILE = original_path

def test_delete_all_conversations(test_client):
    # 1. Create a few conversations
    test_client.post("/api/conversations", json={"title": "Conv 1"})
    test_client.post("/api/conversations", json={"title": "Conv 2"})
    
    # Verify they exist
    resp = test_client.get("/api/conversations")
    assert len(resp.json()) == 2
    
    # 2. Delete all
    del_resp = test_client.delete("/api/conversations")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "all conversations deleted"
    
    # 3. Verify they are gone
    resp = test_client.get("/api/conversations")
    assert resp.json() == []

def test_export_conversations(test_client):
    # 1. Create a conversation
    create_resp = test_client.post("/api/conversations", json={"title": "Export Test"})
    conv_id = create_resp.json()["id"]
    
    # 2. Export
    export_resp = test_client.get("/api/conversations/export")
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    
    # 3. Verify export data
    assert conv_id in export_data
    assert export_data[conv_id]["title"] == "Export Test"
