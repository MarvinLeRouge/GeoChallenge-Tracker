import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const mockPost = vi.hoisted(() => vi.fn());
const mockReplace = vi.hoisted(() => vi.fn());
const mockToastSuccess = vi.hoisted(() => vi.fn());
const mockToastError = vi.hoisted(() => vi.fn());
const mockIsAxiosError = vi.hoisted(() => vi.fn(() => false));

vi.mock("@/api/http", () => ({ default: { post: mockPost } }));
vi.mock("vue-router", () => ({ useRouter: () => ({ replace: mockReplace }) }));
vi.mock("vue-sonner", () => ({
  toast: { success: mockToastSuccess, error: mockToastError },
}));
vi.mock("axios", () => ({ isAxiosError: mockIsAxiosError }));

import Register from "@/pages/auth/Register.vue";

beforeEach(() => {
  vi.clearAllMocks();
  mockIsAxiosError.mockReturnValue(false);
});

/** Fill form fields and trigger submit */
async function fillAndSubmit(
  wrapper: ReturnType<typeof mount>,
  {
    username = "alice",
    email = "alice@example.com",
    password = "Str0ng!",
    confirm = "Str0ng!",
  } = {},
) {
  await wrapper.find('input[autocomplete="username"]').setValue(username);
  await wrapper.find('input[autocomplete="email"]').setValue(email);
  await wrapper.find('input[autocomplete="new-password"]').setValue(password);
  const confirms = wrapper.findAll('input[autocomplete="new-password"]');
  await confirms[1].setValue(confirm);
  await wrapper.find("form").trigger("submit");
  await flushPromises();
}

describe("Register", () => {
  it("shows toast error and aborts when passwords do not match", async () => {
    const wrapper = mount(Register, {
      global: { stubs: { RouterLink: true } },
    });

    await fillAndSubmit(wrapper, { password: "abc", confirm: "xyz" });

    expect(mockPost).not.toHaveBeenCalled();
    expect(mockToastError).toHaveBeenCalledWith(
      "Sécurité du mot de passe",
      expect.any(Object),
    );
  });

  it("posts registration data and redirects to login on success", async () => {
    mockPost.mockResolvedValueOnce({ data: {} });
    const wrapper = mount(Register, {
      global: { stubs: { RouterLink: true } },
    });

    await fillAndSubmit(wrapper);

    expect(mockPost).toHaveBeenCalledWith("/auth/register", {
      username: "alice",
      email: "alice@example.com",
      password: "Str0ng!",
    });
    expect(mockToastSuccess).toHaveBeenCalled();
    expect(mockReplace).toHaveBeenCalledWith("/login");
  });

  it("handles 422 validation error", async () => {
    mockIsAxiosError.mockReturnValue(true);
    mockPost.mockRejectedValueOnce({
      response: {
        status: 422,
        data: {
          detail: [{ msg: "password too weak", loc: ["body", "password"] }],
        },
      },
    });
    const wrapper = mount(Register, {
      global: { stubs: { RouterLink: true } },
    });

    await fillAndSubmit(wrapper);

    expect(mockToastError).toHaveBeenCalledWith(
      "Sécurité du mot de passe",
      expect.any(Object),
    );
  });

  it("handles 422 with non-password field error", async () => {
    mockIsAxiosError.mockReturnValue(true);
    mockPost.mockRejectedValueOnce({
      response: {
        status: 422,
        data: { detail: [{ msg: "invalid email", loc: ["body", "email"] }] },
      },
    });
    const wrapper = mount(Register, {
      global: { stubs: { RouterLink: true } },
    });

    await fillAndSubmit(wrapper);

    expect(mockToastError).toHaveBeenCalledWith(
      "Champs invalides",
      expect.any(Object),
    );
  });

  it("handles 400 weak password error", async () => {
    mockIsAxiosError.mockReturnValue(true);
    mockPost.mockRejectedValueOnce({
      response: { status: 400, data: { detail: "Mot de passe trop court." } },
    });
    const wrapper = mount(Register, {
      global: { stubs: { RouterLink: true } },
    });

    await fillAndSubmit(wrapper);

    expect(mockToastError).toHaveBeenCalledWith(
      "Sécurité du mot de passe",
      expect.any(Object),
    );
  });

  it("handles 409 conflict (duplicate username/email)", async () => {
    mockIsAxiosError.mockReturnValue(true);
    mockPost.mockRejectedValueOnce({
      response: { status: 409, data: {} },
    });
    const wrapper = mount(Register, {
      global: { stubs: { RouterLink: true } },
    });

    await fillAndSubmit(wrapper);

    expect(mockToastError).toHaveBeenCalledWith(
      "Inscription impossible",
      expect.any(Object),
    );
  });

  it("handles unexpected errors gracefully", async () => {
    mockIsAxiosError.mockReturnValue(true);
    mockPost.mockRejectedValueOnce({
      response: { status: 503, data: { detail: "Service unavailable" } },
    });
    const wrapper = mount(Register, {
      global: { stubs: { RouterLink: true } },
    });

    await fillAndSubmit(wrapper);

    expect(mockToastError).toHaveBeenCalledWith("Erreur", expect.any(Object));
  });
});
