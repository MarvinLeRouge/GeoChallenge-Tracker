"""Shared constants for the application."""

# Constants for the D/T (Difficulty/Terrain) matrix
MATRIX_DT_TOTAL_COMBINATIONS = 81  # 9x9 matrix (difficulty 1.0-5.0 × terrain 1.0-5.0 by 0.5)
MATRIX_DT_ROWS_COLS = 9  # Number of rows/columns in the square matrix
MATRIX_DT_MIN_VALUE = 1.0  # Minimum value for difficulty and terrain
MATRIX_DT_MAX_VALUE = 5.0  # Maximum value for difficulty and terrain
MATRIX_DT_STEP = 0.5  # Increment for difficulty and terrain values
