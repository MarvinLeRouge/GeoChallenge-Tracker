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

  it.each([
    ["string_too_long", { max_length: 20 }, "Au plus 20 caractères."],
    ["too_short", { min_length: 1 }, "Au moins 1 éléments."],
    ["too_long", { max_length: 200 }, "Au plus 200 éléments."],
    ["greater_than", { gt: 0 }, "Doit être supérieur à 0."],
    ["greater_than_equal", { ge: 1 }, "Doit être supérieur ou égal à 1."],
    ["less_than", { lt: 90 }, "Doit être inférieur à 90."],
    ["less_than_equal", { le: 50 }, "Doit être inférieur ou égal à 50."],
    ["int_parsing", {}, "Nombre entier attendu."],
    ["float_parsing", {}, "Nombre attendu."],
    ["bool_parsing", {}, "Valeur vrai/faux attendue."],
    ["string_type", {}, "Texte attendu."],
    ["datetime_parsing", {}, "Date invalide."],
    ["datetime_from_date_parsing", {}, "Date invalide."],
    ["enum", { expected: "'a' or 'b'" }, "Valeur attendue : 'a' or 'b'."],
    ["literal_error", { expected: "'x'" }, "Valeur attendue : 'x'."],
    ["json_invalid", {}, "Contenu JSON invalide."],
  ])("traduit le type de validation %s", (type, ctx, expected) => {
    expect(translateValidation(type, ctx)).toBe(expected);
  });

  it("laisse vide une valeur de ctx absente ou un ctx non objet", () => {
    expect(translateValidation("string_too_short", {})).toBe(
      "Au moins  caractères.",
    );
    expect(translateValidation("greater_than", null)).toBe(
      "Doit être supérieur à .",
    );
    expect(translateValidation("less_than", "5")).toBe(
      "Doit être inférieur à .",
    );
  });
});
