import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const mockPost = vi.hoisted(() => vi.fn());
const mockUseRoute = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { post: mockPost } }));
vi.mock("vue-router", () => ({ useRoute: mockUseRoute }));

import VerifyEmail from "@/pages/auth/VerifyEmail.vue";

beforeEach(() => {
  vi.clearAllMocks();
  mockUseRoute.mockReturnValue({ query: { code: "valid-code-123" } });
});

describe("VerifyEmail", () => {
  it("calls verify-email endpoint with code from query on mount, via POST body", async () => {
    mockPost.mockResolvedValueOnce({});
    mount(VerifyEmail, { global: { stubs: { RouterLink: true } } });
    await flushPromises();

    // The code travels in the POST body, not in a query param, so it never
    // shows up in access logs (server-side) or gets sent via Referer header.
    expect(mockPost).toHaveBeenCalledWith("/auth/verify-email", {
      code: "valid-code-123",
    });
  });

  it("shows success message after successful verification", async () => {
    mockPost.mockResolvedValueOnce({});
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

    expect(mockPost).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("invalide");
  });

  it("shows error message when API call fails with detail", async () => {
    mockPost.mockRejectedValueOnce({
      response: { data: { detail: "Le lien a expiré." } },
    });
    const wrapper = mount(VerifyEmail, {
      global: { stubs: { RouterLink: true } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Le lien a expiré.");
  });

  it("shows fallback error message when API fails without detail", async () => {
    mockPost.mockRejectedValueOnce(new Error("Network error"));
    const wrapper = mount(VerifyEmail, {
      global: { stubs: { RouterLink: true } },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("expiré");
  });
});
