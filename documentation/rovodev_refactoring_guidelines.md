# Rovodev - Guide des Bonnes Pratiques de Refactorisation

## 🎯 Règles générales développées lors des refactorisations 2026-01-21

Ce document complète le prompt de base avec les bonnes pratiques éprouvées lors de la transformation majeure du backend GeoChallenge Tracker.

## 🛠️ Méthodologie de refactorisation

### Critères de déclenchement
- **Fichier >300 lignes** avec responsabilités multiples
- **Fonctions >100 lignes** avec logique complexe  
- **Imports circulaires** ou couplage fort
- **Difficulté de test** par manque de modularité

### Phase d'analyse (CRITIQUE pour gros fichiers)
1. **Inventaire exhaustif** : Lister TOUTES les fonctions, leurs responsabilités et usages externes
2. **Matrice de couverture** : Créer un tableau de mapping fonction → nouveau module  
3. **Audit des dépendances** : Identifier tous les fichiers qui importent depuis le fichier à refactoriser
4. **Signatures exactes** : Noter les signatures précises des fonctions publiques

### Architecture modulaire cible

#### Structure standardisée
```
backend/app/
├── domain/
│   ├── models/          # Entités métier (User, Cache, Challenge)
│   └── types/           # Enums, ValueObjects
├── api/
│   ├── dto/             # Schémas d'entrée/sortie API
│   └── routes/          # Endpoints FastAPI
├── services/            # Logique métier organisée en modules
│   ├── user_profile/    # Services complexes en sous-dossiers
│   │   ├── service.py   # Service principal avec injection de dépendances
│   │   ├── validator.py # Validation métier
│   │   └── utils.py     # Utilitaires spécialisés
│   └── *_service.py     # Couches de compatibilité
├── shared/              # Types et utilitaires communs
└── core/                # Configuration, sécurité, logging
```

#### Principes d'architecture
- **Injection de dépendances** : `__init__(self, db: AsyncIOMotorDatabase)`
- **Responsabilité unique** : 1 module = 1 domaine métier
- **Couche de compatibilité** : `*_service.py` exposant les mêmes fonctions publiques
- **Nomenclature claire** : `*_compiler.py`, `*_validator.py`, `*_query.py`

### Méthodologie ultra-prudente (fichiers >500 lignes)

#### Implémentation conservatrice OBLIGATOIRE
1. **Préservation exacte** : Copier la logique sans modifications comportementales
2. **Commentaires "PRESERVATION EXACTE"** : Documenter l'intention de non-modification  
3. **Tests de compatibilité** : Vérifier que tous les imports externes fonctionnent
4. **Validation fonctionnelle** : Aucune perte de fonctionnalité autorisée

#### Workflow de migration
1. Créer la nouvelle structure modulaire
2. Extraire les modules par responsabilité
3. Créer le service principal d'orchestration
4. Créer la couche de compatibilité `*_service.py`
5. Mettre à jour les consommateurs (routes, tests)
6. Validation complète et nettoyage

## 🔍 Qualité du code

### Pre-commit hooks OBLIGATOIRES
Le projet utilise ces hooks - **TOUS doivent passer** :
```bash
- ruff check .          # Linting
- ruff format .         # Formatage  
- mypy .               # Type checking
```

**JAMAIS de commit avec des erreurs ruff ou mypy** - Corriger immédiatement.

### Règles de commits STRICTES
- **Validation pré-commit** : Tous les hooks doivent passer
- **Tests fonctionnels** : Les imports de compatibilité doivent fonctionner après refactorisation
- **Messages descriptifs** : `refactor(services): restructure [module].py into modular architecture`
- **Commits atomiques** : Une modification logique = un commit
- **Pas de `--no-verify`** sauf correction d'erreurs temporaires (rattraper immédiatement)

### Types Python stricts OBLIGATOIRES
- **Annotations complètes** : Toutes les fonctions et méthodes
- **`from __future__ import annotations`** en en-tête
- **`Callable[..., Any]`** au lieu de `callable`
- **`dict[str, Any]`** au lieu de `dict`
- **`list[T]`** au lieu de `List[T]`

## 📚 Documentation des refactorisations

### Format journal.txt
```
--- HH:MM --- [refactoring]  
- Refactorisation [nom_fichier].py ([XXX] lignes) en architecture modulaire
- Fichiers modifiés :
  - backend/app/services/[module]/ : service.py, validator.py, etc.
  - backend/app/services/ : [module]_service.py (compatibilité)
  - backend/app/api/routes/ : [routes_concernées].py
```

### Documentation détaillée OBLIGATOIRE
Créer `documentation/ai_actions/YYYYMMDD_HHMMSS_refactorisation_[module].md` avec :
- **Problème initial** : taille, responsabilités mélangées
- **Architecture proposée** : nouveaux modules et leurs responsabilités  
- **Bénéfices obtenus** : maintenabilité, testabilité, performance
- **Garanties de compatibilité** : API préservée, tests inchangés
- **Validation** : méthode utilisée pour garantir 0 perte fonctionnelle

## 🏆 Exemples de success patterns (2026-01-21)

### Refactorisations réalisées avec succès
1. **Architecture backend** : Séparation domain/api/shared
2. **user_profile.py** (288 lignes) → UserProfileService + LocationParser
3. **targets.py** (838 lignes) → 4 services avec responsabilités uniques
4. **gpx_importer.py** (946 lignes) → 6 modules par domaine
5. **user_challenges.py** (427 lignes) → 5 services focalisés
6. **user_challenge_tasks.py** (730 lignes) → 5 modules ultra-prudents

### Résultat final
**Architecture finale** : **3779 lignes transformées en 25 services modulaires**

### Métriques de réussite
- ✅ **100% de compatibilité** préservée pour toutes les APIs publiques
- ✅ **0 perte fonctionnelle** validée par tests et imports
- ✅ **Pre-commit hooks** passants (ruff + mypy) sur tous les commits
- ✅ **Documentation complète** pour chaque refactorisation
- ✅ **Architecture évolutive** prête pour futurs développements

## ⚠️ Règles ABSOLUES

1. **JAMAIS de refactorisation sans matrice de couverture** pour fichiers >500 lignes
2. **JAMAIS de commit avec erreurs ruff/mypy** 
3. **TOUJOURS créer une couche de compatibilité** pour préserver les imports externes
4. **TOUJOURS documenter** dans journal.txt + ai_actions/
5. **TOUJOURS valider** que les imports de compatibilité fonctionnent après refacto

Ces règles ont permis de transformer avec succès un backend monolithique en architecture modulaire exemplaire, sans aucune régression fonctionnelle.