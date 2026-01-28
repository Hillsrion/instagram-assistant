# Evaluation Module Documentation

Le module `eval/` fournit un pipeline complet pour évaluer la qualité du système RAG. Il distingue clairement deux aspects:

1. **Retrieval** (`eval_retrieval.py`): Teste si les bons chunks sont retrouvés
2. **Generation** (`eval_generation.py`): Teste la qualité des réponses générées par les LLMs

## Structure du Module

```
eval/
├── __init__.py               # Exports des classes principales
├── _cli_utils.py             # Utilitaires CLI partagés
├── generate_dataset.py       # Script: génération de dataset
├── eval_retrieval.py         # Script: évaluation du retrieval
├── eval_generation.py        # Script: évaluation de la génération
├── compare_configs.py        # Script: comparaison de configurations RAG
├── evaluate_summaries.py     # Script: évaluation des résumés
├── benchmark.py              # Bibliothèque: BenchmarkRunner
├── synthetic_generator.py    # Bibliothèque: SyntheticDataGenerator
├── metrics.py                # Bibliothèque: RAGASMetrics
├── eval_dataset.json         # Dataset généré (ignoré par git)
└── eval_dataset.sample.json  # Dataset sample versionné
```

## Quick Start

```bash
# 1. Générer un dataset d'évaluation (50 paires QA)
python -m eval.generate_dataset 50

# 2. Évaluer la qualité du RETRIEVAL
python -m eval.eval_retrieval

# 3. Évaluer la qualité de GÉNÉRATION (comparer des LLMs)
python -m eval.eval_generation qwen3:latest mistral --trials 10 --html

# 4. Comparer différentes configurations RAG
python -m eval.compare_configs
```

## Dataset d'Évaluation

### Localisation
Le dataset est stocké dans `eval/eval_dataset.json` (ignoré par git).

### Sample Versionné
Un fichier sample `eval/eval_dataset.sample.json` est versionné avec des données fictives pour:
- Servir de référence pour le format attendu
- Permettre de tester le pipeline sans données réelles
- Documenter la structure des QA pairs

Pour utiliser le sample:
```bash
cp eval/eval_dataset.sample.json eval/eval_dataset.json
python -m eval.eval_retrieval
```

### Format du Dataset
```json
{
  "metadata": {
    "total_pairs": 50,
    "by_type": {"factual": 17, "summary": 17, "implicit": 16},
    "by_difficulty": {"easy": 15, "medium": 25, "hard": 10}
  },
  "qa_pairs": [
    {
      "question": "Question en langage naturel?",
      "expected_answer": "Réponse attendue basée sur le chunk source",
      "source_chunk_id": "conversation_chunk_001",
      "question_type": "factual",
      "difficulty": "easy",
      "metadata": {
        "participants": ["Alice", "Bob"],
        "date_range": "2024-03-15 - 2024-03-15"
      },
      "tags": []
    }
  ]
}
```

---

## Scripts CLI

### 1. Génération de Dataset (`generate_dataset.py`)

Génère des paires question-réponse synthétiques à partir des chunks indexés.

```bash
python -m eval.generate_dataset 50
python -m eval.generate_dataset --samples 100
```

**Types de questions générées:**
- **Factual**: Extraction directe d'information
- **Summary**: Questions de synthèse
- **Implicit**: Questions nécessitant une inférence

---

### 2. Évaluation du Retrieval (`eval_retrieval.py`)

**Objectif**: Tester si le système RAG retrouve les bons chunks sources.

```bash
# Syntaxe de base
python -m eval.eval_retrieval

# Avec filtres
python -m eval.eval_retrieval --question-type factual,summary
python -m eval.eval_retrieval --difficulty easy,medium
python -m eval.eval_retrieval --participant "Alice"

# Avec modèle juge personnalisé
python -m eval.eval_retrieval --judge qwen3:latest
```

**Métriques calculées:**

| Métrique | Description |
|----------|-------------|
| **Hit@k** | % de questions où le bon chunk est dans le top-k résultats |
| **MRR** | Mean Reciprocal Rank - qualité du classement |
| **Faithfulness** | Fidélité de la réponse aux sources (LLM-as-judge) |
| **Relevance** | Pertinence de la réponse à la question (LLM-as-judge) |

**Output:**
```
=== Benchmark Report: default ===
Total questions: 50

Retrieval Metrics:
  Accuracy (Hit@k): 84.0%
  MRR: 0.762
  Avg Rank: 1.45

Generation Metrics:
  Faithfulness: 78.5%
  Relevance: 82.3%

By Question Type:
  factual: Acc=92.0%, Faith=85.0%
  summary: Acc=76.0%, Faith=72.0%
  implicit: Acc=84.0%, Faith=78.0%
```

---

### 3. Évaluation de la Génération (`eval_generation.py`)

**Objectif**: Comparer la qualité de génération de différents LLMs, indépendamment du retrieval.

Le script fournit directement le chunk source à chaque LLM, isolant ainsi la qualité de génération de la qualité du retrieval.

```bash
# Syntaxe
python -m eval.eval_generation <model1> <model2> [options]

# Exemples
python -m eval.eval_generation qwen3:latest mistral
python -m eval.eval_generation qwen3:latest qwen2.5:3b --trials 10
python -m eval.eval_generation mistral neural-chat --trials 20 --html
python -m eval.eval_generation --models qwen3:latest,mistral --judge qwen3:latest
```

**Options:**

| Option | Description | Défaut |
|--------|-------------|--------|
| `models` | Modèles à comparer (min. 2) | `qwen3:latest qwen2.5:3b` |
| `--trials` | Nombre de questions à tester | 3 |
| `--html` | Générer un rapport HTML interactif | false |
| `--judge` | Modèle juge pour l'évaluation | config.llm_model |

**Métriques calculées:**

| Métrique | Description |
|----------|-------------|
| **Faithfulness** | La réponse est-elle fidèle aux sources fournies? |
| **Relevance** | La réponse répond-elle bien à la question? |
| **Speed** | Vitesse de génération (mots/seconde) |

**Rapport HTML:**

Avec `--html`, un rapport interactif est généré dans `eval/generation_report.html`:
- Graphiques de comparaison
- Détails par question avec réponses côte à côte
- Observations du juge
- Synthèse finale

---

### 4. Comparaison de Configurations (`compare_configs.py`)

Compare plusieurs configurations RAG sur le même dataset (retrieval + génération).

```bash
python -m eval.compare_configs
python -m eval.compare_configs --question-type factual
```

**Configurations comparées par défaut:**

| Config | Query Rewriting | Reranking | Hybrid Search | Context Expansion |
|--------|-----------------|-----------|---------------|-------------------|
| `full` | ✓ | ✓ | ✓ | ✓ |
| `no_reranking` | ✓ | ✗ | ✓ | ✓ |
| `no_hybrid` | ✓ | ✓ | ✗ | ✓ |
| `minimal` | ✗ | ✗ | ✗ | ✗ |

---

## Options de Filtrage

Tous les scripts d'évaluation supportent les mêmes options de filtrage:

| Option | Description | Exemple |
|--------|-------------|---------|
| `--question-type` | Types de questions | `factual,summary,implicit,temporal` |
| `--difficulty` | Niveaux de difficulté | `easy,medium,hard` |
| `--participant` | Filtrer par participant | `"Alice"` |
| `--date-start` | Date de début | `2024-01-01` |
| `--date-end` | Date de fin | `2024-12-31` |
| `--tags` | Filtrer par tags | `important,urgent` |

---

## Utilisation Programmatique

### Générer un Dataset

```python
from rag_pipeline.config import Config
from rag_pipeline.vector_store import VectorStore
from eval import SyntheticDataGenerator

config = Config()
vector_store = VectorStore(config)
vector_store.load()

generator = SyntheticDataGenerator(config)
qa_pairs = generator.generate_dataset(
    vector_store.chunks,
    target_size=50
)
generator.save_dataset(qa_pairs)
```

### Évaluer le Retrieval

```python
from eval import BenchmarkRunner, BenchmarkConfig, SyntheticDataGenerator

config = Config()
generator = SyntheticDataGenerator(config)
qa_pairs = generator.load_dataset()

runner = BenchmarkRunner(config)
bench_config = BenchmarkConfig(
    name="custom",
    use_query_rewriting=True,
    use_reranking=True,
    use_hybrid=True,
    top_k=5
)

report = runner.run_benchmark(qa_pairs, bench_config)
print(report.summary())
```

### Utiliser les Métriques

```python
from eval import RAGASMetrics

metrics = RAGASMetrics(config)

# Score simple
score = metrics.compute_faithfulness(
    question="Qui a dit bonjour?",
    expected_answer="Alice",
    generated_answer="Alice a dit bonjour",
    source_content="Alice: Bonjour!"
)

# Score avec explication (pour les rapports)
result = metrics.compute_faithfulness_with_explanation(...)
# {"score": 0.85, "explanation": "La réponse est fidèle..."}
```

---

## Classes Principales

### QAPair
```python
@dataclass
class QAPair:
    question: str           # La question
    expected_answer: str    # La réponse attendue
    source_chunk_id: str    # ID du chunk source
    question_type: QuestionType  # factual, summary, implicit, temporal
    difficulty: Difficulty  # easy, medium, hard
    metadata: dict          # Métadonnées (participants, date_range)
    tags: List[str]         # Tags optionnels
```

### BenchmarkConfig
```python
@dataclass
class BenchmarkConfig:
    name: str
    use_query_rewriting: bool = True
    use_reranking: bool = True
    use_hybrid: bool = True
    use_context_expansion: bool = True
    top_k: int = 5
```

---

## Fichiers Générés

| Fichier | Description | Versionné |
|---------|-------------|-----------|
| `eval/eval_dataset.json` | Dataset de paires QA | Non |
| `eval/eval_dataset.sample.json` | Sample avec données fictives | Oui |
| `eval/generation_report.html` | Rapport HTML comparaison LLMs | Non |
| `rag_data/benchmark_*.json` | Rapports de benchmark | Non |
| `rag_data/comparison_*.json` | Rapports de comparaison configs | Non |

---

## Bonnes Pratiques

1. **Taille du dataset**: 50-100 paires QA pour des résultats statistiquement significatifs
2. **Diversité**: Assurez-vous que le dataset couvre différents types de questions
3. **Modèle juge**: Utilisez un modèle puissant comme juge (qwen3:latest, mistral)
4. **Baseline**: Comparez toujours avec une configuration "minimal" comme baseline
5. **Séparation des évaluations**:
   - Utilisez `eval_retrieval` pour optimiser le retrieval (embeddings, reranking, hybrid)
   - Utilisez `eval_generation` pour choisir le meilleur LLM de génération
6. **Itération**: Régénérez le dataset après des changements majeurs dans l'enrichissement
