[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# Composables: conventions

This folder contains two types of composables with distinct behaviors.

---

## Composables with state and side effects

These composables manage their own reactive state (`loading`, `error`) and make API calls.
Each call creates a **local, independent** state: two components calling them get two separate states.
To share state across components, prefer a Pinia store (`src/store/`).

| Composable | Role |
| ---------- | ---- |
| `useUserProfile` | Loads and updates the user profile |
| `useUserChallenges` | Paginated list of user challenges |
| `useUserChallenge` | Detail of a single challenge (takes an `id` parameter) |
| `useUserStats` | User statistics |
| `useTargets` | Evaluation, loading, and status of a challenge's targets |
| `useZones` | API calls for the choropleth map (administrative zones) |

---

## Purely logical composables

These composables have no side effects. They encapsulate transformation,
computation, or validation logic. They can be called freely without risking duplicate requests.

| Composable | Role |
| ---------- | ---- |
| `useApiErrorHandler` | Normalizes Axios errors into a readable message |
| `useFormValidation` | Form validation |
| `useCalendarData` | Calendar data transformation (computed) |
| `useMatrixData` | Matrix data transformation (computed) |
| `useMapPopup` | Leaflet popup display logic |
