# Modifications - Système de Logging

## Problème identifié

Vous avez signalé que pour la même question **"qui est ayoub ?"**, l'API retourne:
1. **Parfois**: Juste des statistiques (587 messages, 1 conversation) ❌
2. **Parfois**: Une réponse détaillée avec 15 sources ✅

**Cause probable**: Le `QueryAnalyzer` classe incorrectement la requête comme mode "analytics" au lieu de "retrieval", ce qui routes vers les endpoints de statistiques au lieu du pipeline RAG.

## Solution implémentée

### 1. **Nouveau fichier: `rag_pipeline/logger.py`**
   - Système de logging structuré avec deux niveaux:
     - **Logs traditionnels** (`rag_data/logs/rag_pipeline.log`): Streaming en temps réel
     - **Logs structurés JSONL** (`rag_data/logs/debug.jsonl`): Traces de requêtes complètes par requête

   Classes:
   - `RequestLogger`: Trace chaque requête avec tous ses événements
   - `get_logger()`: Retourne le logger principal

### 2. **Modifications: `rag_pipeline/query_analyzer.py`**
   - Ajout du logger pour tracer:
     - La requête d'entrée
     - Le modèle LLM utilisé
     - La réponse brute du LLM
     - **Le mode détecté (CRUCIAL)**
     - La requête réécrite
     - La plage de dates
     - Les erreurs

   Exemple de log:
   ```
   🔍 Analyzing query: 'qui est ayoub ?'
   Model: ministral-small
   ✅ Analysis complete: mode=retrieval, intent=broad_summary, top_k=15
   ```

### 3. **Modifications: `rag_pipeline/chat.py`**
   - Ajout du `RequestLogger` pour tracer chaque chat:
     - Requête d'entrée
     - Résultats de l'analyse
     - Nombre de sources récupérées
     - Longueur de la réponse LLM
     - Sauvegarde de la trace complète

   Avertissement spécial pour mode analytics:
   ```
   ⚠️ Analytics mode detected for query: 'qui est ayoub ?'
      This should be handled by analytics endpoints, not RAG retrieval
   ```

### 4. **Modifications: `app.py`**
   - Ajout du logger pour tracer les requêtes API
   - **Point critique**: Logging du routage intelligence (analytics vs retrieval)

   Vous verrez maintenant:
   ```
   📨 Chat stream request: 'qui est ayoub ?'
   🎯 Analysis result: mode=analytics, intent=broad_summary
   ⚠️ Routing to ANALYTICS mode for: 'qui est ayoub ?'
     → Using DISCOVERY endpoint
   ```

### 5. **Nouveau script: `view_logs.py`**
   Outil pour consulter les logs facilement:
   ```bash
   python view_logs.py debug         # 10 dernières requêtes
   python view_logs.py tail          # 50 dernières lignes du log
   python view_logs.py search "qui est ayoub"  # Chercher une requête
   python view_logs.py latest        # Dernière requête en détail
   ```

### 6. **Nouveau script: `test_logging.py`**
   Test le système avec 5 requêtes de test et affiche les résultats:
   ```bash
   python test_logging.py
   ```

### 7. **Documentation: `LOGGING_GUIDE.md`**
   Guide complet pour:
   - Comprendre la structure des logs
   - Interpréter les résultats
   - Déboguer le problème
   - Monitorer en temps réel

## Comment utiliser

### Tester le système

```bash
# 1. Tester le logging
python test_logging.py

# 2. Voir les résultats
python view_logs.py debug
```

### Déboguer la requête problématique

```bash
# 1. Envoyer la requête "qui est ayoub ?" via l'API web
# 2. Chercher dans les logs
python view_logs.py search "qui est ayoub"

# 3. Vérifier le champ "mode" dans la sortie
# Si mode=analytics → c'est le problème!
# Si mode=retrieval → classification correcte
```

### Monitorer en temps réel

```bash
tail -f rag_data/logs/rag_pipeline.log
```

Vous verrez chaque requête et sa classification en direct.

## Analyse des logs

### Structure d'un log structuré JSONL

```json
{
  "request_id": "2026-01-28T19:00:45.123456",
  "query": "qui est ayoub ?",
  "duration_seconds": 2.45,
  "event_count": 5,
  "events": [
    {
      "timestamp": "...",
      "type": "query_analysis",
      "data": {
        "mode": "analytics",  // ← LE PROBLÈME SI = "analytics"
        "intent": "broad_summary",
        "rewritten_query": "...",
        "top_k": 15
      }
    },
    {
      "timestamp": "...",
      "type": "retrieval",
      "data": {
        "source_count": 15,
        "top_scores": [0.85, 0.82, ...]
      }
    }
  ]
}
```

### Interprétation

| Mode | Signification | Résultat |
|------|---------------|----------|
| `retrieval` | ✅ Recherche RAG complète | Sources + réponse détaillée |
| `analytics` | ⚠️ Requête de statistiques | Juste des chiffres |

## Prochaines étapes

1. **Exécutez le test** pour confirmer que le logging fonctionne:
   ```bash
   python test_logging.py
   python view_logs.py debug
   ```

2. **Testez la requête problématique** via l'API:
   - Posez "qui est ayoub ?" plusieurs fois
   - Regardez les logs avec `python view_logs.py search "qui est ayoub"`
   - Comparez les résultats de mode

3. **Analysez les données**:
   - Si mode change entre appels → problème dans le QueryAnalyzer
   - Si mode = "analytics" → améliorer le prompt d'analyse
   - Si mode = "retrieval" mais réponse mauvaise → problème dans le retriever

## Fichiers modifiés

- `app.py` - Logging de l'endpoint chat/stream
- `rag_pipeline/chat.py` - Logging du flux chat complet
- `rag_pipeline/query_analyzer.py` - Logging de l'analyse

## Fichiers créés

- `rag_pipeline/logger.py` - Système de logging structuré
- `view_logs.py` - Outil pour consulter les logs
- `test_logging.py` - Script de test
- `LOGGING_GUIDE.md` - Documentation complète
- `LOGGING_CHANGES.md` - Ce fichier

## Notes importantes

✅ **Avantages du logging structuré:**
- Audit trail complet de chaque requête
- Timestamps précis
- Événements structurés en JSON
- Facile à parser et analyser
- Performance minimale

⚠️ **Les logs prennent de la place:**
- Les fichiers s'accumulent dans `rag_data/logs/`
- À nettoyer régulièrement si vous testez beaucoup

🔍 **Pour déboguer efficacement:**
1. Envoyer une requête
2. Regarder les logs immédiatement
3. Vérifier le mode détecté
4. Trouver la cause de la mauvaise classification
