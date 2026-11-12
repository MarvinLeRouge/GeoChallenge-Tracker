/**
 * French messages for the backend `error.code` values (backend/app/core/errors.py `ErrorCode`)
 * and for Pydantic validation `type`s. A unit test checks every backend code is covered.
 */

export const ERROR_MESSAGES: Record<string, string> = {
  // Auth and accounts
  ADMIN_ONLY: "Action réservée aux administrateurs.",
  NOT_AUTHENTICATED: "Vous devez être connecté.",
  INVALID_CREDENTIALS: "Identifiant ou mot de passe incorrect.",
  MISSING_CREDENTIALS: "Identifiant et mot de passe requis.",
  UNVERIFIED_USER:
    "Compte non vérifié : consultez l'email de vérification reçu à l'inscription.",
  INVALID_TOKEN: "Session invalide, veuillez vous reconnecter.",
  NO_REFRESH_TOKEN: "Session expirée, veuillez vous reconnecter.",
  INVALID_REFRESH_TOKEN: "Session expirée, veuillez vous reconnecter.",
  VERIFICATION_CODE_INVALID:
    "Le lien de vérification est invalide ou a expiré.",
  USERNAME_OR_EMAIL_TAKEN: "Nom d'utilisateur ou email déjà utilisé.",
  USER_CREATION_FAILED: "La création du compte a échoué, réessayez plus tard.",
  USER_NOT_FOUND: "Utilisateur introuvable.",
  USER_ID_MISSING: "Identifiant utilisateur manquant.",
  INVALID_USER_ID: "Identifiant utilisateur invalide.",
  PASSWORD_TOO_SHORT: "Le mot de passe doit contenir au moins 8 caractères.",
  PASSWORD_NO_UPPERCASE:
    "Le mot de passe doit contenir au moins une majuscule.",
  PASSWORD_NO_LOWERCASE:
    "Le mot de passe doit contenir au moins une minuscule.",
  PASSWORD_NO_DIGIT: "Le mot de passe doit contenir au moins un chiffre.",
  PASSWORD_NO_SPECIAL:
    "Le mot de passe doit contenir au moins un caractère spécial.",
  FORCE_ADMIN_ONLY:
    "Seuls les administrateurs peuvent forcer le recalcul de la progression.",

  // Rate limiting and generic errors
  RATE_LIMIT_EXCEEDED: "Trop de tentatives, réessayez dans quelques instants.",
  VALIDATION_ERROR: "Certains champs sont invalides.",
  INTERNAL_ERROR: "Une erreur inattendue est survenue.",

  // Uploads and GPX import
  FILE_TOO_LARGE: "Fichier trop volumineux.",
  FILE_DECODE_FAILED: "Impossible de lire le contenu du fichier.",
  GPX_TOO_SMALL: "Fichier trop petit pour être un GPX valide.",
  GPX_MISSING_ROOT:
    "Ce fichier n'est pas un GPX valide (élément <gpx> absent).",
  GPX_FILE_NOT_FOUND: "Fichier GPX introuvable.",
  GPX_FILE_EMPTY: "Le fichier GPX est vide.",
  GPX_READ_FAILED: "Impossible de lire le fichier GPX.",
  GPX_IMPORT_INVALID: "Fichier GPX ou ZIP invalide.",
  ZIP_INVALID: "Archive ZIP invalide.",
  ZIP_NO_GPX: "Aucun fichier GPX valide dans l'archive ZIP.",
  ZIP_TOO_MANY_FILES: "L'archive ZIP contient trop de fichiers (100 maximum).",
  ZIP_TOO_LARGE: "L'archive ZIP décompressée est trop volumineuse.",
  ZIP_EXTRACTION_FAILED: "L'extraction de l'archive ZIP a échoué.",

  // Caches, zones and geo
  CACHE_NOT_FOUND: "Cache introuvable.",
  INVALID_OBJECT_ID: "Identifiant invalide.",
  GEO_INDEX_MISSING:
    "Recherche géographique indisponible (index manquant côté serveur).",
  INVALID_COUNTRY_CODE: "Code pays invalide (2 lettres majuscules, ex. FR).",
  ZONE_UPLOAD_INVALID: "Fichier de zones invalide.",
  ZONE_COUNTRY_REQUIRED: "Le pays est requis pour ce niveau de zone.",
  ZONE_NOT_FOUND: "Zone introuvable.",

  // Profile and challenges
  LOCATION_INVALID: "Position invalide.",
  LOCATION_NOT_FOUND:
    "Aucune position enregistrée : indiquez une position ou enregistrez-la dans votre profil.",
  STATS_NOT_FOUND: "Statistiques introuvables.",
  USER_CHALLENGE_NOT_FOUND: "Challenge introuvable.",
  USER_CHALLENGE_UPDATE_FAILED: "La mise à jour du challenge a échoué.",
  BATCH_TOO_LARGE: "Trop d'éléments à la fois (200 maximum).",
  TASKS_INVALID: "Les tâches sont invalides.",
  TARGETS_RADIUS_REQUIRED: "Le rayon est requis pour filtrer par distance.",

  // Maintenance
  BACKUP_INVALID_PATH: "Chemin de sauvegarde invalide.",
  BACKUP_NOT_FOUND: "Sauvegarde introuvable.",
  BACKUP_ARCHIVE_INVALID: "Archive de sauvegarde invalide.",
  CONFIRMATION_KEY_INVALID: "Clé de confirmation invalide ou expirée.",
  CONFIRMATION_KEY_EXPIRED: "Clé de confirmation expirée, relancez l'analyse.",
  CONFIRMATION_KEY_MISMATCH:
    "La clé de confirmation ne correspond pas à cette sauvegarde.",

  // FastAPI's own errors keep a generic code
  HTTP_401: "Vous devez être connecté.",
  HTTP_403: "Accès refusé.",
  HTTP_404: "Ressource introuvable.",
  HTTP_405: "Action non autorisée.",
};

type Ctx = Record<string, unknown>;

const n = (ctx: Ctx, key: string): string => String(ctx[key] ?? "");

/** French messages for Pydantic validation error types, using their scalar `ctx`. */
const VALIDATION_MESSAGES: Record<string, (ctx: Ctx) => string> = {
  missing: () => "Champ obligatoire.",
  string_too_short: (c) => `Au moins ${n(c, "min_length")} caractères.`,
  string_too_long: (c) => `Au plus ${n(c, "max_length")} caractères.`,
  too_short: (c) => `Au moins ${n(c, "min_length")} éléments.`,
  too_long: (c) => `Au plus ${n(c, "max_length")} éléments.`,
  greater_than: (c) => `Doit être supérieur à ${n(c, "gt")}.`,
  greater_than_equal: (c) => `Doit être supérieur ou égal à ${n(c, "ge")}.`,
  less_than: (c) => `Doit être inférieur à ${n(c, "lt")}.`,
  less_than_equal: (c) => `Doit être inférieur ou égal à ${n(c, "le")}.`,
  int_parsing: () => "Nombre entier attendu.",
  float_parsing: () => "Nombre attendu.",
  bool_parsing: () => "Valeur vrai/faux attendue.",
  string_type: () => "Texte attendu.",
  datetime_parsing: () => "Date invalide.",
  datetime_from_date_parsing: () => "Date invalide.",
  enum: (c) => `Valeur attendue : ${n(c, "expected")}.`,
  literal_error: (c) => `Valeur attendue : ${n(c, "expected")}.`,
  json_invalid: () => "Contenu JSON invalide.",
};

/** French message for a backend error code, or undefined if unknown. */
export const translateErrorCode = (code: unknown): string | undefined =>
  typeof code === "string" ? ERROR_MESSAGES[code] : undefined;

/** French message for a validation detail `type`, or undefined if unknown. */
export const translateValidation = (
  type: unknown,
  ctx: unknown,
): string | undefined => {
  if (typeof type !== "string") return undefined;
  const build = VALIDATION_MESSAGES[type];
  if (!build) return undefined;
  return build(typeof ctx === "object" && ctx !== null ? (ctx as Ctx) : {});
};
