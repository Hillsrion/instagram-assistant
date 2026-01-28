#!/usr/bin/env python3
"""
Script d'aide pour créer le fichier .env avec vos chemins personnalisés.
"""

import os
from pathlib import Path


def main():
    print("=" * 80)
    print("📝 Configuration de l'environnement Instagram Assistant")
    print("=" * 80)
    print()

    env_file = Path(__file__).parent / ".env"

    if env_file.exists():
        response = input("⚠️  Un fichier .env existe déjà. Voulez-vous le recréer ? (y/N): ")
        if response.lower() != 'y':
            print("Annulé.")
            return

    print("Je vais vous poser quelques questions pour configurer vos chemins.\n")

    # Base directory (auto-detect)
    base_dir = Path(__file__).parent
    print(f"✓ Dossier de base détecté: {base_dir}\n")

    # Instagram export directory
    print("1️⃣  Chemin vers votre export Instagram")
    print("   (Dossier contenant les conversations, ex: .../messages/inbox)")
    instagram_export = input("   Chemin: ").strip()
    if not instagram_export:
        instagram_export = str(Path.home() / "Documents/your_instagram_activity/messages/inbox")
        print(f"   → Par défaut: {instagram_export}")

    # Conversations directory
    print("\n2️⃣  Dossier pour stocker les conversations converties (relatif au projet)")
    conversations_dir = input("   Nom (défaut: instagram_conversations): ").strip()
    if not conversations_dir:
        conversations_dir = "instagram_conversations"

    # Index directory
    print("\n3️⃣  Dossier pour stocker les index RAG (relatif au projet)")
    index_dir = input("   Nom (défaut: rag_data): ").strip()
    if not index_dir:
        index_dir = "rag_data"

    # User name
    print("\n4️⃣  Votre prénom (utilisé dans l'interface)")
    user_name = input("   Prénom: ").strip()
    if not user_name:
        user_name = "Ismaël"

    # LLM Model
    print("\n5️⃣  Modèle Ollama à utiliser")
    llm_model = input("   Modèle (défaut: qwen3:latest): ").strip()
    if not llm_model:
        llm_model = "qwen3:latest"

    # Create .env file
    env_content = f"""# Instagram Assistant Configuration
# Généré automatiquement par setup_env.py

# === Chemins Instagram ===
INSTAGRAM_EXPORT_DIR={instagram_export}

# === Chemins du projet ===
BASE_DIR={base_dir}
CONVERSATIONS_DIR={conversations_dir}
INDEX_DIR={index_dir}

# === Configuration utilisateur ===
USER_NAME={user_name}

# === Configuration LLM ===
LLM_MODEL={llm_model}
OLLAMA_URL=http://localhost:11434
LLM_NUM_CTX=8192

# === Configuration Embeddings ===
EMBEDDING_MODEL=BAAI/bge-m3
USE_GPU=true

# === Configuration RAG ===
TOP_K=5
MIN_SIMILARITY=0.3
USE_RERANKING=true
USE_HYBRID=true

# === Configuration Chunking ===
CHUNK_MAX_MESSAGES=50
CHUNK_MAX_DAYS=3
CHUNK_OVERLAP=5
"""

    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)

    print("\n" + "=" * 80)
    print("✅ Fichier .env créé avec succès !")
    print("=" * 80)
    print(f"\n📁 Fichier: {env_file}")
    print("\nVous pouvez modifier ce fichier manuellement si besoin.")
    print("\n🚀 Prochaines étapes:")
    print("   1. Installez les dépendances: pip install -r requirements.txt")
    print("   2. Convertissez vos conversations: python3 instagram_to_text.py")
    print("   3. Créez l'index: python3 setup_rag_batch.py")
    print("   4. Lancez l'application: python3 app.py")


if __name__ == "__main__":
    main()
