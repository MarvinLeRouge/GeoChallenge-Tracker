# Guide d'utilisation - GeoChallenge Tracker

## Présentation

GeoChallenge Tracker est une application web complète pour les passionnés de géocaching. Elle permet de suivre vos challenges personnalisés, d'importer vos trouvailles GPX, de visualiser votre progression et d'obtenir des statistiques sur la complétion de vos défis.

## Authentification

### Inscription
1. Accédez à la page d'inscription
2. Remplissez le formulaire avec vos informations
3. Respectez les critères de sécurité pour votre mot de passe
4. Confirmez votre adresse email via le lien envoyé

### Connexion
1. Accédez à la page de connexion
2. Entrez vos identifiants
3. Vous êtes redirigé vers votre tableau de bord

## Gestion des caches

### Import de fichiers GPX
1. Allez dans le menu "Caches" → "Importer GPX"
2. Sélectionnez votre fichier GPX ou ZIP
3. Choisissez le mode d'import :
   - **Toutes les caches** : Importe toutes les caches du fichier
   - **Caches trouvées** : Importe les caches et les associe à votre compte comme trouvées
4. Le système détecte automatiquement le format (c:geo, Pocket Query)

### Recherche de caches
- Utilisez la recherche par filtres pour trouver des caches selon vos critères
- Filtres disponibles : type, taille, difficulté, terrain, dates, attributs
- Recherche géographique dans une zone rectangulaire ou circulaire

## Challenges

### Challenges personnalisés
- Définissez vos propres challenges avec des critères personnalisés
- Suivez votre progression en temps réel
- Visualisez les caches cibles pour atteindre vos objectifs

### Challenges classiques
#### Matrice D/T
- Vérifiez votre progression dans la matrice 9x9 difficulté/terrain
- Identifiez les combinaisons manquantes
- Visualisez les caches cibles pour compléter la matrice

#### Challenge calendrier
- Suivez votre progression dans le challenge des 365/366 jours
- Identifiez les jours manquants
- Trouvez les caches cibles pour compléter le calendrier

## Suivi de progression

### Statistiques
- Accédez à vos statistiques générales dans "Mes stats"
- Visualisez votre progression au fil du temps
- Consultez des projections de complétion

### Historique
- Suivez l'évolution de vos challenges
- Consultez les snapshots de progression historiques
- Analysez vos tendances

## Profil utilisateur

### Informations personnelles
- Gérez vos informations de profil
- Définissez votre localisation pour des suggestions personnalisées
- Personnalisez vos préférences

## Cartographie

### Visualisation
- Visualisez vos caches trouvées sur la carte
- Consultez les caches cibles pour vos challenges
- Utilisez les outils de dessin pour planifier vos sorties

## Administration (pour les administrateurs)

### Outils de maintenance
- Nettoyage des données orphelines
- Sauvegarde et restauration de la base de données
- Backfill des données d'altitude

### Réimport des attributs de caches
- **Accès** : Réservé aux administrateurs
- **Fonctionnalité** : Réimport des attributs des caches à partir d'un fichier GPX
- **Utilité** : Correction des incohérences dans les attributs des caches dans la base de données
- **Procédure** : Utilisation de la route `/admin/upload-gpx` pour envoyer un fichier GPX
- **Impact** : Met à jour les attributs des caches existants dans la base de données
- **Précautions** : Cette opération peut avoir un impact significatif sur la base de données, à utiliser avec discernement