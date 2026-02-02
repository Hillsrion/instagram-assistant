# Scripts d'Analyse

## analyze_chunks_stats.py

Script d'analyse statistique des chunks pour optimiser la configuration `top_k`.

### Usage

```bash
# Analyse basique
python docs/scripts/analyze_chunks_stats.py

# Avec rapport markdown
python docs/scripts/analyze_chunks_stats.py --output rapport_$(date +%Y%m%d).md

# Spécifier le chemin des chunks
python docs/scripts/analyze_chunks_stats.py --chunks /path/to/chunks.json
```

### Fonctionnalités

- ✅ Analyse de tous les chunks du dataset
- ✅ Distribution par catégorie (léger, moyen, dense, chargé)
- ✅ Calcul des percentiles (P50, P75, P90, P95, P99)
- ✅ Recommandations de `top_k` optimales
- ✅ Projections de budget token pour différentes valeurs
- ✅ Export en format Markdown

### Exemple de Sortie

```
📊 STATISTIQUES GLOBALES
📦 Nombre total de chunks: 32559

📈 Distribution par catégorie:
  • Légers:    22057 ( 67.7%)
  • Moyens:     4791 ( 14.7%)
  • Denses:     2393 (  7.3%)
  • Chargés:    3318 ( 10.2%)

🎯 Tokens par chunk (avec header):
  • Médiane:          214 tokens
  • Moyenne:          375 tokens
  • P95:             1044 tokens
```

### Quand Exécuter

- Après un enrichissement complet du dataset
- Avant de modifier la configuration `top_k`
- Pour valider les hypothèses de dimensionnement
- Périodiquement (mensuel) pour suivre l'évolution

### Rapports Générés

Les résultats d'analyse sont documentés dans :
- `docs/TOP_K_ANALYSIS_REPORT.md` - Rapport complet avec recommandations
- `docs/TOP_K_STATISTICS.md` - Statistiques brutes

### Dernière Analyse

**Date** : 2026-02-02
**Résultat** : 32,559 chunks analysés
**Moyenne** : 375 tokens/chunk
**Recommandation** : top_k=40 pour broad_summary (60% usage)
