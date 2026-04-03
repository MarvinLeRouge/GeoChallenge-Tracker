import { describe, it, expect } from "vitest";
import { useApiErrorHandler } from "@/composables/useApiErrorHandler";

// Build minimal objects that pass isAxiosError() — it checks e.isAxiosError === true
const axiosError = (opts: {
  response?: { status: number; data?: unknown };
  request?: unknown;
  message?: string;
}) => ({
  isAxiosError: true,
  response: opts.response ?? null,
  request: opts.request ?? null,
  message: opts.message ?? "Axios error",
});

describe("handleApiError", () => {
  describe("AxiosError with response", () => {
    it("uses detail as message when present", () => {
      const { handleApiError } = useApiErrorHandler();
      const err = axiosError({
        response: { status: 422, data: { detail: "Champ invalide" } },
      });
      const result = handleApiError(err);
      expect(result.status).toBe(422);
      expect(result.message).toBe("Champ invalide");
      expect(result.detail).toBe("Champ invalide");
    });

    it('falls back to "Erreur <status>" when detail is absent', () => {
      const { handleApiError } = useApiErrorHandler();
      const err = axiosError({ response: { status: 500, data: {} } });
      const result = handleApiError(err);
      expect(result.status).toBe(500);
      expect(result.message).toBe("Erreur 500");
    });

    it('falls back to "Erreur <status>" when data is undefined', () => {
      const { handleApiError } = useApiErrorHandler();
      const err = axiosError({ response: { status: 404 } });
      const result = handleApiError(err);
      expect(result.message).toBe("Erreur 404");
    });
  });

  describe("AxiosError without response (network error)", () => {
    it("returns a network error message", () => {
      const { handleApiError } = useApiErrorHandler();
      const err = axiosError({ request: {} });
      const result = handleApiError(err);
      expect(result.message).toBe(
        "Erreur réseau - impossible de contacter le serveur",
      );
      expect(result.status).toBeUndefined();
    });
  });

  describe("AxiosError without response or request (config error)", () => {
    it("uses the axios error message", () => {
      const { handleApiError } = useApiErrorHandler();
      const err = axiosError({ message: "timeout exceeded" });
      const result = handleApiError(err);
      expect(result.message).toBe("timeout exceeded");
    });

    it("falls back to default message when axios message is empty", () => {
      const { handleApiError } = useApiErrorHandler();
      const err = axiosError({ message: "" });
      const result = handleApiError(err);
      expect(result.message).toBe("Erreur de configuration de la requête");
    });
  });

  describe("non-Axios error", () => {
    it("extracts message from a standard Error", () => {
      const { handleApiError } = useApiErrorHandler();
      const result = handleApiError(new Error("something went wrong"));
      expect(result.message).toBe("something went wrong");
    });

    it('falls back to "Erreur inconnue" for a non-Error value', () => {
      const { handleApiError } = useApiErrorHandler();
      const result = handleApiError(null);
      expect(result.message).toBe("Erreur inconnue");
    });
  });

  describe("error ref", () => {
    it("stores detail in error ref when detail is present", () => {
      const { error, handleApiError } = useApiErrorHandler();
      const err = axiosError({
        response: { status: 400, data: { detail: "Bad request" } },
      });
      handleApiError(err);
      expect(error.value).toBe("Bad request");
    });

    it("stores message in error ref when detail is absent", () => {
      const { error, handleApiError } = useApiErrorHandler();
      handleApiError(new Error("boom"));
      expect(error.value).toBe("boom");
    });
  });
});

describe("clearError", () => {
  it("resets the error ref to empty string", () => {
    const { error, handleApiError, clearError } = useApiErrorHandler();
    handleApiError(new Error("some error"));
    expect(error.value).not.toBe("");
    clearError();
    expect(error.value).toBe("");
  });
});
