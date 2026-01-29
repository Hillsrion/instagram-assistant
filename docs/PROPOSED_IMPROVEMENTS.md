# Améliorations Futures Potentielles

## Stratégies de Recherche

### Recherche Hybride Parallèle (Proactive) 🚀

C'est une stratégie avancée pour gérer les changements de contexte brusques sans latence, proposée pour remplacer ou compléter le "Smart Fallback".

**Le Problème :**
Actuellement, si le `QueryAnalyzer` réécrit une requête en y ajoutant trop de contexte (ex: "Factures" devient "Factures avec Ayoub"), la recherche échoue si l'utilisateur parlait d'autre chose. Le "Smart Fallback" actuel corrige cela mais ajoute potentiellement de la latence (2 recherches séquentielles en cas d'échec).

**La Solution : "Parallel Execution + Reciprocal Rank Fusion (RRF)"**

Au lieu d'attendre l'échec de la première recherche, le système lance **toujours** deux recherches en parallèle :

1.  **Branche Contextuelle :** Recherche avec la requête réécrite par le LLM (Optimisée pour le suivi de conversation).
2.  **Branche Brute :** Recherche avec la requête utilisateur originale (Optimisée pour le changement de sujet).

**Algorithme de Fusion (RRF) :**
On combine les résultats des deux branches.
- Si un document apparaît dans les deux listes, son score augmente significativement.
- Si un document n'apparaît que dans la branche "Brute" (car le sujet a changé) avec un fort score, il remonte naturellement en tête de liste, surpassant les résultats faibles de la branche contextuelle.

**Avantages :**
*   **Expérience Utilisateur Fluide :** Latence constante, pas d'attente "double" visible pour l'utilisateur.
*   **Robustesse Maximale :** Gère automatiquement et implicitement l'ambiguïté entre "Même sujet" et "Nouveau sujet" sans heuristique complexe.

**Inconvénients :**
*   **Coût de calcul :** Double le nombre de recherches vectorielles (embeddings + search) par message utilisateur.

**Pistes d'Implémentation Technique :**
*   Utiliser `asyncio.gather` dans `app.py` pour lancer les deux `retriever.retrieve()` simultanément.
*   Implémenter une fonction de fusion RRF standard (ex: `score = 1 / (rank + k)`) ou une moyenne pondérée des scores de similarité.
