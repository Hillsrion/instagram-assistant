# Configuration de l'environnement

Ce projet utilise maintenant un système de configuration basé sur des variables d'environnement pour éviter les chemins en dur dans le code.

## Configuration rapide

### Option 1 : Script interactif (recommandé)

```bash
python3 setup_env.py
```

Le script vous guidera pour configurer tous les paramètres nécessaires.

### Option 2 : Copie manuelle

```bash
# 1. Copier le template
cp .env.example .env

# 2. Éditer avec vos chemins
nano .env  # ou vim, code, etc.
```

## Variables d'environnement

### Chemins essentiels

| Variable | Description | Exemple |
|----------|-------------|---------|
| `INSTAGRAM_EXPORT_DIR` | Dossier de votre export Instagram (inbox) | `~/Documents/instagram/messages/inbox` |
| `BASE_DIR` | Dossier racine du projet (auto-détecté) | `/Users/username/instagram-assistant` |
| `CONVERSATIONS_DIR` | Dossier des conversations converties | `instagram_conversations` (relatif) |
| `INDEX_DIR` | Dossier des index RAG | `rag_data` (relatif) |

### Configuration utilisateur

| Variable | Description | Défaut |
|----------|-------------|--------|
| `USER_NAME` | Votre prénom | `Ismaël` |

### Configuration LLM

| Variable | Description | Défaut |
|----------|-------------|--------|
| `LLM_MODEL` | Modèle Ollama | `qwen3:latest` |
| `OLLAMA_URL` | URL du serveur Ollama | `http://localhost:11434` |

### Configuration Embeddings

| Variable | Description | Défaut |
|----------|-------------|--------|
| `EMBEDDING_MODEL` | Modèle d'embeddings | `BAAI/bge-m3` |
| `USE_GPU` | Utiliser GPU si disponible | `true` |

### Configuration RAG

| Variable | Description | Défaut |
|----------|-------------|--------|
| `TOP_K` | Nombre de chunks récupérés | `5` |
| `MIN_SIMILARITY` | Score minimum de similarité | `0.3` |
| `USE_RERANKING` | Activer le reranking | `true` |
| `USE_HYBRID` | Activer recherche hybride | `true` |

### Configuration Chunking

| Variable | Description | Défaut |
|----------|-------------|--------|
| `CHUNK_MAX_MESSAGES` | Messages max par chunk | `50` |
| `CHUNK_MAX_DAYS` | Durée max d'un chunk (jours) | `3` |
| `CHUNK_OVERLAP` | Chevauchement entre chunks | `5` |

## Outils d'analyse et statistiques

Le projet inclut désormais des outils d'analyse dans le dossier `utils/` :

| Script | Description |
|--------|-------------|
| `python3 utils/rag_stats.py` | Analyse statistique détaillée (conversations, messages, chunks) |
| `python3 utils/top_20_messages.py` | Affiche les 20 conversations les plus volumineuses |

## Scripts d'indexation avancés

### setup_rag_batch.py

Le script d'indexation principal supporte de nouveaux flags :

| Flag | Description |
|------|-------------|
| `--limit N` | Limite l'indexation aux N premières conversations (utile pour tester rapidement) |
| `--import-test` | Importe automatiquement le dataset de test depuis `test_conversations/` |
| `--reset` | Supprime tout l'index et recommence à zéro |
| `--status` | Affiche l'état actuel de l'indexation |

Exemple :
```bash
# Importer les données de test et indexer seulement 5 conversations
python3 setup_rag_batch.py --import-test --limit 5 --reset
```

## Workflow complet

### Première utilisation

```bash
# 1. Configurer l'environnement
python3 setup_env.py

# 2. Installer les dépendances (inclut python-dotenv)
pip install -r requirements.txt

# 3. Convertir vos conversations
python3 instagram_to_text.py

# 4. Créer l'index
python3 setup_rag_batch.py

# 5. Lancer l'app
python3 app.py
```

### Merge de plusieurs exports

Si vous avez plusieurs exports Instagram (ancien + nouveau) :

```bash
# 1. Merger les exports
python3 merge_instagram_exports.py \
    ~/Documents/export_juin_2024/messages/inbox \
    ~/Documents/export_dec_2024/messages/inbox \
    -o ~/Documents/instagram_merged/messages/inbox

# 2. Mettre à jour votre .env
# Changer INSTAGRAM_EXPORT_DIR vers le dossier mergé
nano .env

# 3. Convertir et indexer
python3 instagram_to_text.py
python3 update_index.py
```

### Mise à jour avec un nouvel export

```bash
# 1. Merger avec l'ancien export
python3 merge_instagram_exports.py \
    ~/Documents/instagram_merged/messages/inbox \
    ~/Documents/nouvel_export/messages/inbox \
    -o ~/Documents/instagram_merged_v2/messages/inbox

# 2. Mettre à jour INSTAGRAM_EXPORT_DIR dans .env

# 3. Reconvertir et mettre à jour l'index
python3 instagram_to_text.py
python3 update_index.py
```

## Chemins relatifs vs absolus

- **Chemins relatifs** : Si vous spécifiez un nom simple (ex: `instagram_conversations`), il sera relatif à `BASE_DIR`
- **Chemins absolus** : Commencent par `/` (Unix) ou `C:\` (Windows), utilisés tels quels

Exemples :
```bash
# Relatif au projet
CONVERSATIONS_DIR=instagram_conversations
# → /Users/username/projet/instagram_conversations

# Absolu
CONVERSATIONS_DIR=/Users/username/custom/location
# → /Users/username/custom/location
```

## Sécurité

Le fichier `.env` contient vos chemins personnels et **ne doit jamais être commité sur Git**.

Il est déjà dans `.gitignore` :
```
# Environment Variables
.env
.env.local
.env.*.local
```

## Dépannage

### Le script ne trouve pas mes conversations

Vérifiez que `INSTAGRAM_EXPORT_DIR` pointe vers le bon dossier :
```bash
ls "$INSTAGRAM_EXPORT_DIR"
# Devrait lister vos dossiers de conversations
```

### Variables d'environnement non chargées

Assurez-vous que `python-dotenv` est installé :
```bash
pip install python-dotenv
```

### Erreur "module 'dotenv' not found"

```bash
pip install --upgrade python-dotenv
```

## Logique d'import automatique

Le script `instagram_to_text.py` a été amélioré pour détecter automatiquement vos exports Instagram. Il cherche dans l'ordre de priorité suivant :

1. La variable d'environnement `INSTAGRAM_EXPORT_DIR` (si définie)
2. Le dossier `merged_instagram_export/` (créé par `merge_instagram_exports.py`)
3. Les dossiers dans `original_import_folders/`
4. Tout dossier commençant par `instagram-` dans la racine

Cette logique permet de gérer facilement des exports multiples ou fusionnés sans reconfiguration constante.

## Migration depuis l'ancienne version

Si vous utilisez une version précédente avec des chemins hardcodés :

1. Lancez `python3 setup_env.py`
2. Vos données existantes dans `instagram_conversations/` et `rag_data/` seront automatiquement utilisées
3. Aucune réindexation n'est nécessaire

Les chemins par défaut correspondent aux anciens emplacements hardcodés.
