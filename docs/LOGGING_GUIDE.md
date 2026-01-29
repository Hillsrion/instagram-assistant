# Guide de Logging pour le Pipeline RAG

## Vue d'ensemble

Un système de logging structuré a été ajouté pour déboguer les problèmes de classification de requêtes. Ce guide explique comment y accéder et l'interpréter.

## Fichiers de log

### 1. `rag_data/logs/rag_pipeline.log`
Log principal du pipeline en temps réel. Contient tous les événements avec timestamps et niveaux (DEBUG, INFO, WARNING, ERROR).

**Exemple:**
```
[2026-01-28 19:00:45,123] INFO     rag_pipeline - 📨 Chat stream request: 'qui est ayoub ?'
[2026-01-28 19:00:45,234] DEBUG    rag_pipeline - [analysis] mode: retrieval, intent: broad_summary
[2026-01-28 19:00:45,456] INFO     rag_pipeline - 🔄 Using RETRIEVAL flow
```

### 2. `rag_data/logs/debug.jsonl`
Format JSONL (JSON Lines) avec une trace structurée par requête. Chaque ligne est un objet JSON complet avec tous les événements d'une requête.

**Exemple de structure:**
```json
{
  "request_id": "2026-01-28T19:00:45.123456",
  "query": "qui est ayoub ?",
  "duration_seconds": 2.45,
  "event_count": 5,
  "events": [
    {
      "timestamp": "2026-01-28T19:00:45.234",
      "type": "query_analysis",
      "data": {
        "mode": "analytics",
        "intent": "broad_summary",
        "rewritten_query": "Who is Ayoub?",
        "top_k": 15
      }
    },
    {
      "timestamp": "2026-01-28T19:00:45.456",
      "type": "retrieval",
      "data": {
        "source_count": 12,
        "top_scores": [0.85, 0.82, 0.79]
      }
    }
  ]
}
```

## Utiliser le script `view_logs.py`

### Afficher les derniers logs
```bash
python view_logs.py debug        # Les 10 dernières requêtes
python view_logs.py debug 20     # Les 20 dernières requêtes
```

### Afficher les logs RAG en temps réel
```bash
python view_logs.py tail         # Les 50 dernières lignes
python view_logs.py tail 100     # Les 100 dernières lignes
```

### Chercher une requête spécifique
```bash
python view_logs.py search "qui est ayoub"
python view_logs.py search "combien de messages"
```

### Voir la dernière requête en détail
```bash
python view_logs.py latest
```

## Interpréter les logs

### Le problème à déboguer

Vous avez signalé que pour la question **"qui est ayoub ?"**:
- **Réponse 1 (mauvaise):** Juste des stats (587 messages, 1 conversation)
- **Réponse 2 (correcte):** Réponse détaillée avec 15 sources

### Tracer dans les logs

1. **Cherchez votre requête:**
   ```bash
   python view_logs.py search "qui est ayoub"
   ```

2. **Regardez le champ `mode`:**
   ```
   MODE: analytics | INTENT: broad_summary  ← PROBLÈME!
   MODE: retrieval | INTENT: broad_summary  ← CORRECT
   ```

3. **Si mode = "analytics":**
   - La requête a été mal classifiée
   - Elle a été routée vers `handle_discovery_query` ou `handle_computational_query`
   - Résultat: juste des stats, pas de RAG retrieval

4. **Si mode = "retrieval":**
   - La classification est correcte
   - Le pipeline RAG complet s'exécute
   - Sources et réponse complète

### Événements importants

| Type d'événement | Signification | Clé importante |
|-----------------|---------------|----------------|
| `query_analysis` | Analyse de la requête par LLM | `mode` (analytics/retrieval) |
| `retrieval` | Récupération de sources | `source_count` |
| `llm_response` | Génération de réponse | `response_length` |
| `error` | Erreur dans le pipeline | `message` |

## Cas d'étude: "qui est ayoub ?"

### La requête
```
"qui est ayoub ?"
```

### Réponses observées
1. Mode analytics → Réponse: "Ayoub ait-addi: 587 messages, 1 conversations" ❌
2. Mode retrieval → Réponse: Détail complet avec sources ✅

### Raison probable
Le prompt du QueryAnalyzer dit:
```python
"analytics' = compter le TOTAL de messages, conversations ou contacts
 Exemples: 'Combien j'ai de messages ?', 'Nombre de messages avec Marie ?', 'Liste mes contacts'"
```

Pour "qui est ayoub ?", le LLM doit décider:
- **analytics**: "C'est une question sur une personne, donc compter ses messages?"
- **retrieval**: "C'est une question sémantique, chercher qui est Ayoub dans les conversations"

Le problème est que le prompt du QueryAnalyzer est ambigu ou inconsistant.

## Solution recommandée

1. **Améliorer le prompt du QueryAnalyzer** (rag_pipeline/query_analyzer.py):
   - Clarifier ce qui est "analytics" vs "retrieval"
   - Ajouter plus d'exemples pour les questions "qui est..."

2. **Ajouter de la télémétrie** (already done!):
   - Logs structurés pour déboguer chaque décision

3. **Monitorer les résultats**:
   ```bash
   python view_logs.py search "qui est"
   # Vérifier que mode=retrieval pour toutes ces questions
   ```

## Options de log en temps réel

### Pendant le développement
Laissez le log principal ouvert dans un terminal:
```bash
tail -f rag_data/logs/rag_pipeline.log
```

Vous verrez chaque requête en temps réel:
```
[19:00:45] INFO - 📨 Chat stream request: 'qui est ayoub ?'
[19:00:45] INFO - 🎯 Analysis result: mode=analytics, intent=broad_summary
[19:00:45] WARNING - ⚠️ Routing to ANALYTICS mode for: 'qui est ayoub ?'
```

### Analyser les traces structurées après
```bash
python view_logs.py debug 20
# Examine chaque requête avec ses événements détaillés
```

## Niveaux de log

- **DEBUG**: Détails techniques (LLM response, paramètres)
- **INFO**: Événements importants (analyse, récupération, réponse)
- **WARNING**: ⚠️ Comportement inattendu (mode analytics pour une question factuelle)
- **ERROR**: ❌ Erreur dans le pipeline

## Configuration du logging

Pour modifier les niveaux de log, éditez `rag_pipeline/logger.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Changer ici: DEBUG, INFO, WARNING, ERROR
    # ...
)
```

## Résumé

Le système de logging permet de:
1. ✅ Tracer chaque requête de bout en bout
2. ✅ Identifier la classification (analytics vs retrieval)
3. ✅ Déboguer les problèmes rapidement
4. ✅ Archiver les traces pour l'analyse

**Prochaine étape:** Utilisez `python view_logs.py search "qui est ayoub"` après avoir testé la requête pour voir pourquoi elle est classifiée différemment selon l'appel.
