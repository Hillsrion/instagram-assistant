# Instagram Assistant - Guide de Démarrage Rapide

## Prérequis

- Python 3.10+
- Ollama avec un modèle installé (ex: `qwen3:latest`)
- Fichiers de conversation Instagram au format `.txt`

## Installation

```bash
# Cloner le projet
git clone <repo-url>
cd instagram-assistant

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt
```

## Configuration

Éditer `rag_pipeline/config.py` si nécessaire :

```python
# Chemins
base_dir: Path = Path("/chemin/vers/instagram-assistant")

# Modèle LLM (Ollama)
llm_model: str = "qwen3:latest"
ollama_url: str = "http://localhost:11434"

# Votre nom (pour identifier vos messages)
user_name: str = "VotreNom"

# Seuil de confiance (0.25 = 25%)
confidence_threshold: float = 0.25

# Filtrage PII activé
enable_pii_filter: bool = True
```

## Indexation initiale

### 1. Préparer les conversations

Placez vos fichiers `.txt` dans `instagram_conversations/`.

Format attendu :
```
# Conversation Instagram avec Alice
ID: conversation_123
Participants: VotreNom, Alice
============================================================

[2024-01-15 10:00:00] Alice: Salut !
[2024-01-15 10:01:00] VotreNom: Hey, ça va ?
...
```

### 2. Lancer l'indexation

```bash
python setup_rag_batch.py
```

Cela va :
1. Découper les conversations en chunks
2. Enrichir les chunks avec des résumés et questions
3. Générer les embeddings
4. Construire l'index FAISS, BM25 et métadonnées

**Durée** : ~1-2 min pour 50 conversations

## Utilisation

### Interface Web

```bash
python app.py
```

Ouvrir http://localhost:8000 dans votre navigateur.

### Interface CLI

```bash
python cli.py
```

Tapez vos questions directement dans le terminal.

### Mise à jour incrémentale

Après avoir ajouté/modifié des fichiers :

```bash
# Voir les changements détectés
python update_index.py --status

# Appliquer les changements
python update_index.py
```

## Évaluation

### Générer un dataset de test

```bash
python -m eval.run_eval --generate 50
```

### Lancer un benchmark

```bash
python -m eval.run_eval --benchmark
```

### Comparer les configurations

```bash
python -m eval.run_eval --compare
```

## Commandes utiles

| Commande | Description |
|----------|-------------|
| `python app.py` | Lancer le serveur web |
| `python cli.py` | Interface en ligne de commande |
| `python setup_rag_batch.py` | Indexation complète |
| `python update_index.py` | Mise à jour incrémentale |
| `python update_index.py --status` | Voir les changements |
| `python update_index.py --full` | Reconstruction complète |
| `python -m eval.run_eval --generate N` | Générer N paires QA |
| `python -m eval.run_eval --benchmark` | Benchmark |
| `python -m eval.run_eval --compare` | Comparaison configs |

## Structure des données

```
rag_data/
├── faiss_index/
│   ├── index.faiss      # Index vectoriel
│   └── chunks.json      # Métadonnées des chunks
├── bm25_index.pkl       # Index BM25
├── metadata.db          # SQLite métadonnées
├── file_state.json      # État des fichiers (delta tracker)
├── enrichment_state.json # État de l'enrichissement
├── eval_dataset.json    # Dataset d'évaluation
└── conversations.json   # Historique des conversations web
```

## Dépannage

### "Index FAISS non trouvé"

Lancez l'indexation initiale :
```bash
python setup_rag_batch.py
```

### "Impossible de se connecter à Ollama"

Vérifiez qu'Ollama tourne :
```bash
ollama serve
```

### Réponses de mauvaise qualité

1. Augmentez le `top_k` dans la config
2. Vérifiez que le seuil de confiance n'est pas trop élevé
3. Relancez l'enrichissement des chunks

### Mise à jour incrémentale ne détecte rien

Les modifications sont détectées par hash du contenu. Si seule la date a changé, le fichier n'est pas considéré comme modifié.

Pour forcer :
```bash
python update_index.py --full
```

## Ressources

- [Documentation des fonctionnalités](FEATURES.md)
- [Référence API](API.md)
- [Roadmap](../ROADMAP_PRO.md)
