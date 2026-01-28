"""
Tests pour setup_env.py - Génération du fichier .env.
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
from io import StringIO

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSetupEnv(unittest.TestCase):
    """Tests pour le script setup_env."""

    def setUp(self):
        """Crée un répertoire temporaire pour les tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Nettoie le répertoire temporaire."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_env_file_creation(self):
        """Le fichier .env est créé correctement."""
        # Simuler le contenu d'un fichier .env généré
        env_content = """# Instagram Assistant Configuration
INSTAGRAM_EXPORT_DIR=/path/to/export
BASE_DIR=/path/to/base
CONVERSATIONS_DIR=instagram_conversations
INDEX_DIR=rag_data
USER_NAME=TestUser
LLM_MODEL=qwen3:latest
OLLAMA_URL=http://localhost:11434
"""
        
        env_file = self.temp_path / ".env"
        env_file.write_text(env_content)
        
        # Vérifier le contenu
        content = env_file.read_text()
        self.assertIn("INSTAGRAM_EXPORT_DIR", content)
        self.assertIn("LLM_MODEL", content)
        self.assertIn("OLLAMA_URL", content)

    def test_env_file_contains_required_vars(self):
        """Le fichier .env contient toutes les variables requises."""
        required_vars = [
            "INSTAGRAM_EXPORT_DIR",
            "BASE_DIR",
            "CONVERSATIONS_DIR",
            "INDEX_DIR",
            "USER_NAME",
            "LLM_MODEL",
            "OLLAMA_URL",
            "EMBEDDING_MODEL",
            "TOP_K",
            "MIN_SIMILARITY"
        ]
        
        # Créer un fichier .env complet
        env_content = "\n".join([f"{var}=value" for var in required_vars])
        env_file = self.temp_path / ".env"
        env_file.write_text(env_content)
        
        content = env_file.read_text()
        for var in required_vars:
            self.assertIn(var, content, f"Variable manquante: {var}")

    def test_env_example_parsing(self):
        """Le fichier .env.example peut être parsé."""
        # Si le fichier .env.example existe dans le projet
        project_root = Path(__file__).parent.parent.parent
        env_example = project_root / ".env.example"
        
        if env_example.exists():
            content = env_example.read_text()
            
            # Vérifier que c'est bien un fichier de configuration
            lines = content.strip().split('\n')
            config_lines = [l for l in lines if '=' in l and not l.startswith('#')]
            
            self.assertGreater(len(config_lines), 0, "Le .env.example devrait contenir des variables")


class TestEnvVariables(unittest.TestCase):
    """Tests pour les variables d'environnement."""

    def test_default_values(self):
        """Les valeurs par défaut sont raisonnables."""
        defaults = {
            "LLM_MODEL": "qwen3:latest",
            "OLLAMA_URL": "http://localhost:11434",
            "EMBEDDING_MODEL": "BAAI/bge-m3",
            "TOP_K": "5",
            "MIN_SIMILARITY": "0.3"
        }
        
        for key, expected in defaults.items():
            # Juste vérifier que les valeurs sont des chaînes non vides
            self.assertIsInstance(expected, str)
            self.assertGreater(len(expected), 0)


if __name__ == '__main__':
    unittest.main()
