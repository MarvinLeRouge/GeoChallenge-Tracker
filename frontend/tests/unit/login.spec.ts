import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const mockLogin = vi.hoisted(() => vi.fn());
const mockReplace = vi.hoisted(() => vi.fn());
const mockHandleApiError = vi.hoisted(() => vi.fn());
const mockClearError = vi.hoisted(() => vi.fn());
const mockRouteQuery = vi.hoisted(() => ({}) as Record<string, string>);

vi.mock("@/store/auth", () => ({
  useAuthStore: () => ({ login: mockLogin }),
}));

vi.mock("vue-router", () => ({
  useRouter: () => ({ replace: mockReplace }),
  useRoute: () => ({ query: mockRouteQuery }),
}));

vi.mock("@/composables/useApiErrorHandler", () => ({
  useApiErrorHandler: () => ({
    error: null,
    handleApiError: mockHandleApiError,
    clearError: mockClearError,
  }),
}));

import Login from "@/pages/auth/Login.vue";

beforeEach(() => {
  vi.clearAllMocks();
  // Reset route query for each test
  Object.keys(mockRouteQuery).forEach(
    (k) => delete (mockRouteQuery as Record<string, string>)[k],
  );
});

describe("Login", () => {
  it("calls auth.login with form values on submit", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    const wrapper = mount(Login);

    await wrapper.find('input[name="identifier"]').setValue("user@example.com");
    await wrapper.find('input[name="password"]').setValue("secret123");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(mockLogin).toHaveBeenCalledWith({
      identifier: "user@example.com",
      password: "secret123",
    });
  });

  it('redirects to "/" when no redirect query param', async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    const wrapper = mount(Login);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(mockReplace).toHaveBeenCalledWith("/");
  });

  it("redirects to the redirect query param after login", async () => {
    mockRouteQuery.redirect = "/my/challenges";
    mockLogin.mockResolvedValueOnce(undefined);
    const wrapper = mount(Login);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(mockReplace).toHaveBeenCalledWith("/my/challenges");
  });

  it("calls handleApiError on failed login", async () => {
    const err = new Error("Invalid credentials");
    mockLogin.mockRejectedValueOnce(err);
    const wrapper = mount(Login);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(mockHandleApiError).toHaveBeenCalledWith(err);
  });

  it("clears previous error before each submission", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    const wrapper = mount(Login);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(mockClearError).toHaveBeenCalled();
  });
});
