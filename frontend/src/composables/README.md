# Composables — Conventions

Ce dossier contient deux types de composables aux comportements distincts.

---

## Composables avec état et effets de bord

Ces composables gèrent leur propre état réactif (`loading`, `error`) et effectuent des appels API.
Chaque appel crée un état **local et indépendant** — deux composants qui les appellent obtiennent deux états séparés.
Pour partager l'état entre composants, préférer un store Pinia (`src/store/`).

| Composable | Rôle |
|---|---|
| `useUserProfile` | Chargement et mise à jour du profil utilisateur |
| `useUserChallenges` | Liste paginée des challenges utilisateur |
| `useUserChallenge` | Détail d'un challenge (prend un `id` en paramètre) |
| `useUserStats` | Statistiques utilisateur |

---

## Composables purement logiques

Ces composables n'ont pas d'effets de bord. Ils encapsulent de la logique de transformation,
de calcul ou de validation. Ils peuvent être appelés librement sans risque de doublon de requête.

| Composable | Rôle |
|---|---|
| `useApiErrorHandler` | Normalise les erreurs Axios en message lisible |
| `useFormValidation` | Validation de formulaires |
| `useCalendarData` | Transformation des données calendrier (computed) |
| `useMatrixData` | Transformation des données matrice (computed) |
| `useMapPopup` | Logique d'affichage des popups Leaflet |
