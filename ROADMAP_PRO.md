# Roadmap RAG - Passage à l'échelle "Industrielle"

Ce document liste les améliorations nécessaires pour transformer le projet d'assistant Instagram (déjà au niveau Expert algorithmique) en une solution de niveau Production/Industriel.

## 1. Pipeline d'Évaluation (PRIORITÉ 1) 🧪
Permettre de mesurer objectivement la qualité du RAG à chaque modification de code.

- [ ] **Générateur de Dataset de Test (Synthetic Data Generation)**
    - Créer un script qui utilise un LLM puissant pour lire des chunks aléatoires et générer des couples (Question, Réponse, Source ID).
    - Viser un dataset de ~50 questions variées (factuelles, résumés, détails implicites).
- [ ] **Métriques Automatiques (RAGAS)**
    - Implémenter le calcul de la *Retrieval Accuracy* (est-ce que le bon document est dans le top 5 ?).
    - Implémenter le calcul de la *Faithfulness* (est-ce que la réponse est fidèle à la source ?).
- [ ] **Benchmarking**
    - Comparer les performances avec/sans Query Rewriting.
    - Comparer les performances avec/sans Questions Hypothétiques.

## 2. Robustesse & Confiance 🛡️
Éviter les réponses fausses ou floues et économiser des ressources.

- [ ] **Seuils de Rejet (Confidence Thresholds)**
    - Analyser les scores du Cross-Encoder.
    - Définir un seuil (ex: < 0.25) en dessous duquel le système répond immédiatement "Je ne sais pas" sans appeler le LLM génératif.
- [ ] **Gestion des "Non-Réponses"**
    - Améliorer le prompt système pour qu'il soit encore plus strict sur les refus de répondre.
- [ ] **Filtrage de Contenu**
    - Détecter et masquer les informations sensibles (adresses, numéros de téléphone) dans les réponses (PII Redaction).

## 3. Mise à jour Incrémentale (Data Engineering) 🔄
Ne plus avoir à tout ré-indexer à chaque fois.

- [ ] **Détection de Changements (Delta Indexing)**
    - Stocker le hash/timestamp de chaque fichier de conversation.
    - Ne lancer le pipeline d'indexation (très coûteux en LLM) que sur les nouveaux fichiers ou fichiers modifiés.
- [ ] **Append-Only Vector Store**
    - Modifier `VectorStore` pour permettre l'ajout de nouveaux vecteurs sans reconstruire tout l'index FAISS.

## 4. Expérience Utilisateur (UX) ✨
Rendre l'outil plus agréable et interactif.

- [ ] **Citations Interactives (Web UI)**
    - Dans l'interface Web, rendre les citations `[1]` cliquables pour ouvrir une modale affichant le texte source exact.
- [ ] **Questions Suggérées (Follow-up Questions)**
    - Après chaque réponse, demander au LLM de générer 3 boutons de questions de suite logiques.
- [ ] **Streaming Amélioré**
    - Afficher les étapes de réflexion ("Recherche...", "Lecture de 5 documents...", "Génération...") pendant l'attente.

## 5. Optimisation Performance (Optionnel) 🚀
- [ ] **Cache de Requêtes**
    - Mettre en cache les résultats des requêtes fréquentes (Exact Match Cache).
- [ ] **Quantization**
    - Explorer l'usage de modèles d'embedding quantizés pour réduire l'empreinte mémoire si le dataset dépasse 100k chunks.
