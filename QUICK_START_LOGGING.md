# Quick Start - Système de Logging

## En 2 minutes

### 1. Tester le logging
```bash
python test_logging.py
```

Cela va:
- Tester 5 requêtes différentes
- Créer les logs dans `rag_data/logs/`
- Afficher les résultats

### 2. Voir les logs générés
```bash
python view_logs.py debug
```

Vous devriez voir quelque chose comme:
```
🔹 Request #1
   ID: 2026-01-28T19:00:45.123456
   Query: qui est ayoub ?
   ├─ [ANALYSIS] mode=analytics, intent=broad_summary
   │  └─ top_k=15, rewritten=Who is Ayoub?
```

## 3. Déboguer votre requête

**Lancez l'API:**
```bash
python app.py
```

**Dans un autre terminal, surveillez les logs:**
```bash
tail -f rag_data/logs/rag_pipeline.log
```

**Testez la requête problématique via l'API web** ou avec curl:
```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "qui est ayoub ?", "conversation_id": null}'
```

**Cherchez la requête dans les logs structurés:**
```bash
python view_logs.py search "qui est ayoub"
```

## 4. Interpréter les résultats

Regardez le champ `MODE`:

```
MODE: retrieval   ✅ BON - Utilise RAG
MODE: analytics   ⚠️  PROBLÈME - Utilise juste les stats
```

## Commandes utiles

```bash
# Voir les 10 dernières requêtes
python view_logs.py debug

# Voir les 50 dernières requêtes
python view_logs.py debug 50

# Voir le log principal en temps réel
tail -f rag_data/logs/rag_pipeline.log

# Chercher une requête spécifique
python view_logs.py search "qui est"

# Voir la dernière requête en détail
python view_logs.py latest
```

## Structure des logs

```
rag_data/logs/
├── rag_pipeline.log        # Log traditionnel (temps réel)
└── debug.jsonl             # Traces structurées (analyse)
```

## Où trouver l'aide

- **Guide complet**: `LOGGING_GUIDE.md`
- **Documentation des changements**: `LOGGING_CHANGES.md`
- **Test automatisé**: `test_logging.py`
- **Outil de visualisation**: `view_logs.py`

## Problème connu

Si vous voyez:
```
⚠️  Analytics mode detected for query: 'qui est ayoub ?'
```

Cela veut dire que le QueryAnalyzer a mal classifié la requête. C'est exactement le problème qu'on cherche à déboguer avec le logging!

## Astuce

Pour voir les logs en direct pendant que vous testez:

**Terminal 1:**
```bash
python app.py
```

**Terminal 2:**
```bash
tail -f rag_data/logs/rag_pipeline.log | grep -i "qui est"
```

**Terminal 3:**
```bash
# Testez votre requête
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "qui est ayoub ?"}'
```

Vous verrez le flux complet en temps réel!
