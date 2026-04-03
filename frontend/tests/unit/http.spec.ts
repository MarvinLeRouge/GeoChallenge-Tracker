import { describe, it, expect } from "vitest";
import type { FastAPIValidationItem } from "@/types/http";
import { getDetail, detailToText } from "@/utils/http";

describe("http utils (FastAPI detail)", () => {
  it("retourne le detail string", () => {
    expect(getDetail({ detail: "Not authenticated" })).toBe(
      "Not authenticated",
    );
  });

  it("retourne les items de validation si array", () => {
    const arr: FastAPIValidationItem[] = [
      { loc: ["body", "password"], msg: "too weak" },
    ];
    expect(getDetail({ detail: arr })).toEqual(arr);
    expect(detailToText(arr)).toBe("too weak");
  });

  it("retombe sur msg si detail absent", () => {
    expect(getDetail({ msg: "Username or email already used" })).toBe(
      "Username or email already used",
    );
  });

  it("renvoie undefined si objet sans champs exploitables", () => {
    expect(getDetail({ foo: "bar" })).toBeUndefined();
    expect(detailToText(undefined)).toBe("");
  });

  // ✅ nouvelles branches couvertes :

  it("renvoie undefined si entrée non-objet (string/null/number)", () => {
    expect(getDetail("oops")).toBeUndefined();
    expect(getDetail(null)).toBeUndefined();
    expect(getDetail(42)).toBeUndefined();
  });

  it("ignore un detail non conforme (array sans items valides)", () => {
    // pas de msg/loc => pas un FastAPIValidationItem
    expect(getDetail({ detail: [{}] })).toBeUndefined();
    // msg non-string => non valide
    expect(getDetail({ detail: [{ msg: 123 }] as unknown })).toBeUndefined();
    // loc non-array => non valide
    expect(
      getDetail({ detail: [{ loc: "password" }] as unknown }),
    ).toBeUndefined();
  });

  it("detailToText retourne le string directement (branche string)", () => {
    expect(detailToText("message d'erreur")).toBe("message d'erreur");
  });

  it("detailToText filtre les items sans msg (branche ?? '')", () => {
    const arr = [
      { loc: ["body"], msg: "first error" },
      { loc: ["query"] } as unknown as FastAPIValidationItem, // msg absent
    ];
    expect(detailToText(arr)).toBe("first error");
  });
});
