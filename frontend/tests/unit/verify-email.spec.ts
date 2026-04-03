import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const mockGet = vi.hoisted(() => vi.fn());
const mockUseRoute = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));
vi.mock("vue-router", () => ({ useRoute: mockUseRoute }));

import VerifyEmail from "@/pages/auth/VerifyEmail.vue";

beforeEach(() => {
  vi.clearAllMocks();
  mockUseRoute.mockReturnValue({ query: { code: "valid-code-123" } });
});

describe("VerifyEmail", () => {
  it("calls verify-email endpoint with code from query on mount", async () => {
    mockGet.mockResolvedValueOnce({});
    mount(VerifyEmail, { global: { stubs: { RouterLink: true } } });
    await flushPromises();

    expect(mockGet).toHaveBeenCalledWith("/auth/verify-email", {
      params: { code: "valid-code-123" },
    });
  });

  it("shows success message after successful verification", async () => {
    mockGet.mockResolvedValueOnce({});
    const wrapper = mount(VerifyEmail, {
      global: { stubs: { RouterLink: true } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("vérifiée");
  });

  it("shows error when no code is in the query", async () => {
    mockUseRoute.mockReturnValue({ query: {} });
    const wrapper = mount(VerifyEmail, {
      global: { stubs: { RouterLink: true } },
    });
    await flushPromises();

    expect(mockGet).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("invalide");
  });

  it("shows error message when API call fails with detail", async () => {
    mockGet.mockRejectedValueOnce({
      response: { data: { detail: "Le lien a expiré." } },
    });
    const wrapper = mount(VerifyEmail, {
      global: { stubs: { RouterLink: true } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Le lien a expiré.");
  });

  it("shows fallback error message when API fails without detail", async () => {
    mockGet.mockRejectedValueOnce(new Error("Network error"));
    const wrapper = mount(VerifyEmail, {
      global: { stubs: { RouterLink: true } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("expiré");
  });
});
