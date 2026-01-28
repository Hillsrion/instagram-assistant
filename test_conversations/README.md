# Dataset de Conversations de Test

Ce dossier contient un dataset diversifié de conversations Instagram pour tester le système RAG.

## Vue d'ensemble

**Total de conversations** : 10
**Nombre de messages** : ~1,100 messages au total

## Conversations incluses

### 1. Sarah - Amie Proche
- **Fichier** : `sarah_amie_proche_1234567890.txt`
- **Messages** : 156
- **Période** : Mars 2024 - Janvier 2025
- **Type de relation** : Amitié proche
- **Émotions** : Joie, stress, soutien émotionnel, excitation, tristesse
- **Sujets** : Séries TV, travail, brunch, relations amoureuses, fiançailles, organisation mariage
- **Caractéristiques** : Conversation moyenne-longue, émotions variées, sujets multiples

### 2. Lucas - Collègue
- **Fichier** : `lucas_collegue_2345678901.txt`
- **Messages** : 87
- **Période** : Septembre 2024 - Janvier 2025
- **Type de relation** : Professionnelle/collègue amical
- **Émotions** : Neutre, amical, collaboratif
- **Sujets** : Projets de travail, présentations, télétravail, sport
- **Caractéristiques** : Ton professionnel mais friendly, échanges pratiques

### 3. Maman - Famille
- **Fichier** : `maman_3456789012.txt`
- **Messages** : 243
- **Période** : Janvier 2024 - Janvier 2025
- **Type de relation** : Familiale (mère-fils)
- **Émotions** : Affection, tendresse, inquiétude maternelle
- **Sujets** : Santé, repas, visites familiales, nouvelle relation, vacances, Noël
- **Caractéristiques** : Très affectueuse, longue période, relation profonde

### 4. Groupe Vacances Portugal
- **Fichier** : `groupe_vacances_4567890123.txt`
- **Messages** : 8
- **Période** : 22 novembre 2024 (même jour)
- **Type de relation** : Groupe d'amis
- **Émotions** : Excitation, enthousiasme
- **Sujets** : Organisation voyage, réservation vols
- **Caractéristiques** : Très court, efficace, coordination rapide

### 5. Maxime - Urgence Médicale
- **Fichier** : `urgence_maxime_5678901234.txt`
- **Messages** : 32
- **Période** : 3 août 2024 (3h-9h du matin)
- **Type de relation** : Ami proche
- **Émotions** : Peur, stress intense, panique, soulagement
- **Sujets** : Urgence médicale grand-mère, hôpital
- **Caractéristiques** : Situation de crise, émotions fortes, soutien

### 6. Alex - Meilleur Ami Gaming
- **Fichier** : `alex_bestfriend_6789012345.txt`
- **Messages** : 67
- **Période** : Décembre 2024
- **Type de relation** : Meilleure amitié
- **Émotions** : Joie, fun, légèreté
- **Sujets** : Memes, jeux vidéo, PS5, cinéma, Noël
- **Caractéristiques** : Très léger, humour, blagues, langage informel

### 7. Emma - Relation Amoureuse
- **Fichier** : `emma_relation_7890123456.txt`
- **Messages** : 124
- **Période** : Septembre 2024 - Janvier 2025
- **Type de relation** : Couple
- **Émotions** : Amour, romance, tendresse
- **Sujets** : Rendez-vous, restaurant, présentation aux parents, fiançailles
- **Caractéristiques** : Romantique, évolution de la relation, jalons importants

### 8. Léa - Conflit et Réconciliation
- **Fichier** : `dispute_lea_8901234567.txt`
- **Messages** : 45
- **Période** : 12-18 juillet 2024
- **Type de relation** : Amies
- **Émotions** : Colère, tristesse, blessure, pardon
- **Sujets** : Dispute à propos d'exclusion, jalousie, réconciliation
- **Caractéristiques** : Conflit, émotions négatives puis positives, résolution

### 9. Pierre - Annulation Simple
- **Fichier** : `annulation_9012345678.txt`
- **Messages** : 4
- **Période** : 15 novembre 2024 (3 minutes)
- **Type de relation** : Amis/connaissances
- **Émotions** : Neutre, compréhensif
- **Sujets** : Annulation de plans
- **Caractéristiques** : Très court, échange pratique minimal

### 10. Sophie - Collaboration Photographe
- **Fichier** : `collaboration_photographe_0123456789.txt`
- **Messages** : 94
- **Période** : Octobre - Décembre 2024
- **Type de relation** : Professionnelle créative
- **Émotions** : Enthousiasme créatif, satisfaction professionnelle
- **Sujets** : Shootings photo, collaboration artistique, succès
- **Caractéristiques** : Professionnelle mais passionnée, créativité

### 11. Team Mariage Laura
- **Fichier** : `organisation_mariage_1234567890.txt`
- **Messages** : 187
- **Période** : Juin - Septembre 2024
- **Type de relation** : Groupe d'amis proches
- **Émotions** : Joie, excitation, stress, entraide, amour
- **Sujets** : Organisation mariage, fiançailles, déco, traiteur, résolution de problèmes
- **Caractéristiques** : Longue conversation de groupe, collaboration, événement majeur

## Statistiques Globales

### Longueur des conversations
- **Très courtes** (< 10 messages) : 2 conversations
- **Courtes** (10-50 messages) : 2 conversations
- **Moyennes** (50-100 messages) : 3 conversations
- **Longues** (100-200 messages) : 3 conversations
- **Très longues** (> 200 messages) : 1 conversation

### Types de relations
- **Amicales proches** : 4
- **Professionnelles** : 2
- **Familiales** : 1
- **Romantiques** : 1
- **Groupes** : 2
- **Conflits** : 1

### Émotions principales
- **Positives** : Joie, amour, excitation, enthousiasme, satisfaction
- **Négatives** : Stress, peur, colère, tristesse, panique
- **Neutres** : Coordination, professionnel, pratique

### Thèmes abordés
- Travail et carrière
- Relations amoureuses
- Famille
- Événements (mariages, fêtes, Noël)
- Loisirs (gaming, cinéma, photographie)
- Urgences et crises
- Voyages
- Conflits et réconciliation
- Créativité et collaboration

## Cas d'usage pour les tests

### Tests de recherche
- **Recherche temporelle** : Questions sur des dates spécifiques, périodes
- **Recherche de participants** : Trouver conversations avec certaines personnes
- **Recherche thématique** : Trouver conversations sur travail, amour, famille, etc.

### Tests d'émotions
- **Émotions positives** : sarah, alex, emma, sophie, laura
- **Émotions négatives** : maxime, lea
- **Émotions mixtes** : sarah, maman, laura

### Tests de longueur
- **Conversations courtes** : pierre, groupe_vacances
- **Conversations moyennes** : lucas, alex, maxime, lea, sophie
- **Conversations longues** : sarah, emma, maman, laura

### Tests de complexité
- **Simples** : pierre, groupe_vacances
- **Moyennes** : lucas, alex, maxime
- **Complexes** : sarah, lea, emma, sophie, laura, maman

## Utilisation

Ces conversations peuvent être utilisées pour :
1. Tester le système de chunking
2. Tester la recherche sémantique
3. Tester les filtres de métadonnées
4. Tester la génération de résumés
5. Tester l'identification d'émotions
6. Tester les questions hypothétiques
7. Tester la recherche BM25
8. Tester le reranking

## Notes

- Toutes les conversations suivent le format Instagram standard
- Les conversations contiennent des réactions, médias et liens variés
- Les dates sont réalistes et cohérentes
- Les noms et IDs sont fictifs
- Le contenu est varié et représentatif de vraies conversations
