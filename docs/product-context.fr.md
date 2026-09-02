🇫🇷 Version française | [🇬🇧 English version](product-context.md)

---

# Contexte produit : GeoChallenge Tracker

**Date de création :** 2026-09-02
**Type :** Référence produit, contexte produit durable maintenu au fil du code
**Périmètre :** Ensemble du produit (audience, positionnement, capacités, engagements de marque et d'accessibilité)

> Ce document est le miroir public et versionné du contexte produit du projet. Un fichier compagnon, `PRODUCT.md` à la racine du dépôt, est gitignoré et sert de point d'entrée lisible par machine pour le skill de design/produit utilisé pendant le développement ; son contenu est reproduit ici.

---

## Plateforme

Web.

## Stack technique

Codebase existante, pas un projet greenfield : Vue 3 + TypeScript + Vite, Tailwind CSS 3 (avec le plugin Flowbite et les composants `flowbite-vue`), Pinia pour l'état, `vue-router`, Leaflet (+ `leaflet-draw`, `leaflet.markercluster`) pour les cartes, Heroicons et Lucide pour les icônes, `vue-sonner` pour les notifications. Le backend est FastAPI + MongoDB, consommé en REST via axios.

## Utilisateurs

Utilisateur principal : un géocacheur passionné et autonome qui définit et suit des challenges personnalisés (ex. une matrice D/T 9x9, un challenge calendrier sur 365 jours) et souhaite remplacer des tableurs et notes éparpillés par un outil unique. Usage solo, le produit ne vise pas actuellement les clubs ni la coordination de groupe.

## Objectif produit

Permet aux géocacheurs d'importer leurs finds et caches connues depuis des exports GPX, de détecter automatiquement les caches de type challenge parmi elles, de définir les règles d'un challenge dans un langage de tâches dédié, et de suivre la progression de complétion (y compris projections et suggestions de caches cibles) plutôt que de tenir des tableurs manuellement.

## Positionnement

La détection automatique de challenges à partir de données GPX importées, combinée à un langage dédié pour décrire les règles/tâches des challenges et au suivi automatique de progression, est le différenciateur central face aux alternatives génériques (tableurs classiques, Project-GC, GSAK).

## Contexte d'usage

- Usage solo, web desktop et mobile.
- Données source : fichiers GPX exportés depuis Geocaching.com (finds, et caches dans une zone).
- Types de challenges classiques déjà supportés : matrice D/T (9x9), challenge calendrier (365 jours), plus des challenges personnalisés via le langage de description de tâches.
- Workflows basés sur la carte : recherche de caches par rayon/bbox, visualisation des zones, identification des caches cibles qui font le plus avancer un challenge.
- Audience principale : la communauté francophone du géocaching (France + autres pays francophones) ; les textes d'interface sont en français. Aucune expansion internationale/anglophone prévue à court terme.

## Capacités et contraintes

- Authentification : inscription/connexion/rafraîchissement, vérification d'email par code.
- Caches : import GPX/ZIP synchrone, recherche par bbox/rayon/filtres avancés, recherche par code GC ou id Mongo.
- Challenges : créés à partir des caches ; les user-challenges supportent le listing, le patch par item, et la vérification matrice D/T et calendrier.
- Cibles : évaluation, listing, recherche de proximité.
- Statistiques : projections de complétion.
- Mode sombre : la préférence utilisateur `dark_mode` (modèle utilisateur backend) est entièrement implémentée côté frontend via des variantes Tailwind `dark:` sur toutes les pages, avec une persistance gérée par un store `theme` dédié (`frontend/src/store/theme.ts`).

## Engagements de marque

- Nom du produit : "GeoChallenge Tracker".
- Une gamme de couleur `gold` est déjà engagée dans `tailwind.config.ts` (50-900, ancrée sur `#FFD700`), une couleur de marque volontaire, cohérente avec le géocaching/la chasse au trésor, à préserver et développer, pas à remplacer.

## Éléments disponibles

De vraies captures d'écran du produit existent dans `docs/screenshots/` (recherche de caches par rayon et bbox, matrice D/T filtrée/non filtrée, challenge calendrier filtré/non filtré) et sont intégrées dans le README. Aucun témoignage client, étude de cas ou presse n'existe, ne rien fabriquer sur ce point.

## Principes produit

1. Remplacer le suivi de challenges par tableur par une détection automatique et un calcul de progression, l'outil doit toujours faire le comptage, jamais l'utilisateur.
2. Voix French-first, geocaching-literate : utiliser le vocabulaire propre à la communauté (code GC, D/T, FTF, matrice, challenge calendrier) plutôt qu'une phraséologie SaaS générique.
3. Les vues carte et données doivent rester lisibles en conditions réelles, en extérieur/sur mobile, pas seulement à un bureau.
4. Préserver l'identité visuelle or/chasse au trésor existante ; l'étendre délibérément plutôt que la génériciser.
5. Workflows solo-first : aucune décision de design ne doit présumer un contexte d'équipe ou d'édition partagée, sauf si explicitement cadré plus tard.

## Accessibilité et inclusion

Aucun standard d'accessibilité formellement confirmé pour l'instant. Lacune connue signalée dans le backlog produit existant : les détails d'un jour du challenge calendrier ne sont exposés que via un attribut `title` au survol, invisible sur écran tactile et faible pour les lecteurs d'écran, une vraie contrainte que les prochains travaux sur le calendrier devront traiter, pas encore une exigence documentée plus largement.
