---
description: Utilisation des Git Worktrees pour le développement de fonctionnalités
---

Ce workflow décrit comment utiliser les `git worktree` pour isoler le développement d'une nouvelle fonctionnalité dans un dossier séparé, permettant de garder le répertoire principal propre.

### 1. Création d'un Worktree

Pour commencer à travailler sur une nouvelle branche dans un worktree dédié :

// turbo
```bash
git branch feature/nom-de-la-feature
git worktree add .worktree/nom-de-la-feature feature/nom-de-la-feature
```

### 2. Développement

Travailler dans le dossier `.worktree/nom-de-la-feature`. Les dépendances doivent être gérées localement si nécessaire (ex: `pnpm install` dans le dossier frontend du worktree).

### 3. Commit des changements

Une fois le travail terminé, commiter les changements depuis l'intérieur du dossier du worktree :

// turbo
```bash
git add .
git commit -m "feat: description de la fonctionnalité"
```

### 4. Fusion et Nettoyage

Depuis le répertoire **principal** de l'application :

// turbo
```bash
# S'assurer d'être sur la branche cible (ex: dev)
git checkout dev

# Mettre à jour la branche de fonctionnalité via rebase (recommandé)
git checkout feature/nom-de-la-feature
git rebase dev
git checkout dev
git merge feature/nom-de-la-feature --ff-only

# Alternative direct (rebase interactif ou simple)
# git rebase dev feature/nom-de-la-feature

# Supprimer le worktree
git worktree remove .worktree/nom-de-la-feature

# Supprimer la branche locale
git branch -d feature/nom-de-la-feature
```

> [!NOTE]
> Toujours utiliser le préfixe `.worktree/` pour que les dossiers soient ignorés par Git (si configuré dans .gitignore).
