/** Constantes partagées pour l'application frontend */

// Constantes pour la matrice D/T (Difficulty/Terrain)
export const MATRIX_DT_TOTAL_COMBINATIONS = 81; // 9x9 matrix (difficulty 1.0-5.0 × terrain 1.0-5.0 by 0.5)
export const MATRIX_DT_ROWS_COLS = 9; // Nombre de lignes/colonnes dans la matrice carrée
export const MATRIX_DT_MIN_VALUE = 1.0; // Valeur minimale pour difficulté et terrain
export const MATRIX_DT_MAX_VALUE = 5.0; // Valeur maximale pour difficulté et terrain
export const MATRIX_DT_STEP = 0.5; // Incrément pour les valeurs de difficulté et terrain