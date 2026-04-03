import { describe, it, expect, vi, beforeEach } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const mockGet = vi.hoisted(() => vi.fn());
const mockPost = vi.hoisted(() => vi.fn());

vi.mock("@/api/http", () => ({ default: { get: mockGet, post: mockPost } }));

import { useAuthStore } from "@/store/auth";

const makeTokenResponse = () => ({ access_token: "tok123" });
const makeProfileApi = () => ({
  _id: "u1",
  username: "alice",
  email: "a@b.com",
});
const makeLocation = () => ({ lat: 48.8, lon: 2.3 });

beforeEach(() => {
  setActivePinia(createPinia());
  sessionStorage.clear();
  vi.clearAllMocks();
});

describe("setTokens", () => {
  it("stores access_token in state and sessionStorage", () => {
    const store = useAuthStore();
    store.setTokens(makeTokenResponse());
    expect(store.accessToken).toBe("tok123");
    expect(sessionStorage.getItem("access_token")).toBe("tok123");
  });

  it("handles missing access_token gracefully", () => {
    const store = useAuthStore();
    store.setTokens({ access_token: "" });
    expect(store.accessToken).toBe("");
  });
});

describe("isAuthenticated", () => {
  it("is false when accessToken is empty", () => {
    const store = useAuthStore();
    expect(store.isAuthenticated).toBe(false);
  });

  it("is true when accessToken is set", () => {
    const store = useAuthStore();
    store.setTokens(makeTokenResponse());
    expect(store.isAuthenticated).toBe(true);
  });
});

describe("login", () => {
  it("sets tokens and fetches profile after successful login", async () => {
    mockPost.mockResolvedValueOnce({ data: makeTokenResponse() });
    mockGet
      .mockResolvedValueOnce({ data: makeProfileApi() })
      .mockResolvedValueOnce({ data: makeLocation() });
    const store = useAuthStore();

    await store.login({ identifier: "alice", password: "pass" });

    expect(store.accessToken).toBe("tok123");
    expect(store.user?.username).toBe("alice");
  });

  it("posts with URL-encoded body and correct content-type", async () => {
    mockPost.mockResolvedValueOnce({ data: makeTokenResponse() });
    mockGet.mockResolvedValue({ data: {} });
    const store = useAuthStore();

    await store.login({ identifier: "alice", password: "pass" });

    const [, body, config] = mockPost.mock.calls[0];
    expect(body).toBeInstanceOf(URLSearchParams);
    expect(config.headers["Content-Type"]).toBe(
      "application/x-www-form-urlencoded",
    );
  });
});

describe("refresh", () => {
  it("updates tokens from refresh endpoint", async () => {
    mockPost.mockResolvedValueOnce({ data: { access_token: "newTok" } });
    const store = useAuthStore();

    await store.refresh();

    expect(store.accessToken).toBe("newTok");
    expect(sessionStorage.getItem("access_token")).toBe("newTok");
  });
});

describe("logout", () => {
  it("clears token, user, and sessionStorage", () => {
    const store = useAuthStore();
    store.setTokens(makeTokenResponse());
    store.logout();
    expect(store.accessToken).toBe("");
    expect(store.user).toBeNull();
    expect(sessionStorage.getItem("access_token")).toBeNull();
  });
});

describe("init", () => {
  it("is a no-op when already initialized", async () => {
    const store = useAuthStore();
    store.initialized = true;
    await store.init();
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("does nothing when no token in sessionStorage", async () => {
    const store = useAuthStore();
    await store.init();
    expect(store.initialized).toBe(true);
    expect(mockGet).not.toHaveBeenCalled();
  });

  it("fetches profile when token exists in sessionStorage", async () => {
    sessionStorage.setItem("access_token", "existing-token");
    mockGet
      .mockResolvedValueOnce({ data: makeProfileApi() })
      .mockResolvedValueOnce({ data: makeLocation() });
    const store = useAuthStore();

    await store.init();

    expect(store.accessToken).toBe("existing-token");
    expect(mockGet).toHaveBeenCalledTimes(2);
  });
});
