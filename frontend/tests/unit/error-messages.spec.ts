import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  ERROR_MESSAGES,
  translateErrorCode,
  translateValidation,
} from "@/utils/errorMessages";

const backendCodes = (): string[] => {
  const src = readFileSync(
    resolve(__dirname, "../../../backend/app/core/errors.py"),
    "utf-8",
  );
  return [...src.matchAll(/^ {4}([A-Z_]+) = "\1"$/gm)].map((m) => m[1]);
};

describe("error messages", () => {
  it("couvre chaque ErrorCode du backend", () => {
    const codes = backendCodes();
    expect(codes.length).toBeGreaterThan(50);
    expect(codes.filter((c) => !(c in ERROR_MESSAGES))).toEqual([]);
  });

  it("traduit un code connu et ignore un code inconnu", () => {
    expect(translateErrorCode("GPX_TOO_SMALL")).toBe(
      "Fichier trop petit pour être un GPX valide.",
    );
    expect(translateErrorCode("NOPE")).toBeUndefined();
    expect(translateErrorCode(undefined)).toBeUndefined();
  });

  it("traduit un type de validation avec son ctx", () => {
    expect(translateValidation("string_too_short", { min_length: 8 })).toBe(
      "Au moins 8 caractères.",
    );
    expect(translateValidation("missing", undefined)).toBe(
      "Champ obligatoire.",
    );
    expect(translateValidation("value_error", {})).toBeUndefined();
    expect(translateValidation(42, {})).toBeUndefined();
  });
});
