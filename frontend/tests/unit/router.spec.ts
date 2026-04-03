import { describe, it, expect, vi, beforeEach } from "vitest";

// Capture the guard functions registered by the router module
const capturedBefore = vi.hoisted(() => ({
  fn: null as ((to: unknown) => unknown) | null,
}));
const capturedAfter = vi.hoisted(() => ({
  fn: null as ((to: unknown) => void) | null,
}));
const capturedScroll = vi.hoisted(() => ({
  fn: null as ((to: unknown, from: unknown, saved: unknown) => unknown) | null,
}));

const mockAuthState = vi.hoisted(() => ({
  isAuthenticated: false,
  init: vi.fn(),
}));

vi.mock("@/store/auth", () => ({
  useAuthStore: () => mockAuthState,
}));

vi.mock("vue-router", () => ({
  createRouter: vi.fn((options: { scrollBehavior: unknown }) => {
    capturedScroll.fn = options.scrollBehavior as (
      to: unknown,
      from: unknown,
      saved: unknown,
    ) => unknown;
    return {
      beforeEach: vi.fn((fn: (to: unknown) => unknown) => {
        capturedBefore.fn = fn;
      }),
      afterEach: vi.fn((fn: (to: unknown) => void) => {
        capturedAfter.fn = fn;
      }),
    };
  }),
  createWebHistory: vi.fn(() => ({})),
}));

// Importing the module triggers createRouter + guard registration
import "@/router";

const makeRoute = (
  name: string,
  path = `/${name}`,
  fullPath = path,
  hash = "",
  meta: Record<string, unknown> = {},
) => ({ name, path, fullPath, hash, meta });

beforeEach(() => {
  mockAuthState.isAuthenticated = false;
  vi.clearAllMocks();
});

describe("beforeEach navigation guard", () => {
  it("calls auth.init() on every navigation", async () => {
    await capturedBefore.fn!(makeRoute("home", "/"));
    expect(mockAuthState.init).toHaveBeenCalledOnce();
  });

  it("allows unauthenticated access to home", async () => {
    const result = await capturedBefore.fn!(makeRoute("home", "/"));
    expect(result).toBeUndefined();
  });

  it("allows unauthenticated access to auth/login", async () => {
    const result = await capturedBefore.fn!(makeRoute("auth/login", "/login"));
    expect(result).toBeUndefined();
  });

  it("allows unauthenticated access to auth/register", async () => {
    const result = await capturedBefore.fn!(
      makeRoute("auth/register", "/register"),
    );
    expect(result).toBeUndefined();
  });

  it("allows unauthenticated access to auth/verify-email", async () => {
    const result = await capturedBefore.fn!(
      makeRoute("auth/verify-email", "/verify-email"),
    );
    expect(result).toBeUndefined();
  });

  it("allows unauthenticated access to legal", async () => {
    const result = await capturedBefore.fn!(makeRoute("legal", "/legal"));
    expect(result).toBeUndefined();
  });

  it("allows unauthenticated access to 404", async () => {
    const result = await capturedBefore.fn!(makeRoute("404", "/not-found"));
    expect(result).toBeUndefined();
  });

  it("allows unauthenticated access to /help/* prefix routes", async () => {
    const result = await capturedBefore.fn!(
      makeRoute("help-page", "/help/overview"),
    );
    expect(result).toBeUndefined();
  });

  it("redirects unauthenticated user to login for protected routes", async () => {
    const route = makeRoute("userChallengeList", "/my/challenges");
    const result = await capturedBefore.fn!(route);
    expect(result).toEqual({
      name: "auth/login",
      query: { redirect: "/my/challenges" },
    });
  });

  it("redirects unauthenticated user to login for targets", async () => {
    const route = makeRoute("my-targets", "/my/targets");
    const result = await capturedBefore.fn!(route);
    expect(result).toEqual({
      name: "auth/login",
      query: { redirect: "/my/targets" },
    });
  });

  it("redirects authenticated user away from login to home", async () => {
    mockAuthState.isAuthenticated = true;
    const result = await capturedBefore.fn!(makeRoute("auth/login", "/login"));
    expect(result).toEqual({ path: "/" });
  });

  it("redirects authenticated user away from register to home", async () => {
    mockAuthState.isAuthenticated = true;
    const result = await capturedBefore.fn!(
      makeRoute("auth/register", "/register"),
    );
    expect(result).toEqual({ path: "/" });
  });

  it("allows authenticated user to navigate to protected routes", async () => {
    mockAuthState.isAuthenticated = true;
    const result = await capturedBefore.fn!(
      makeRoute("userChallengeList", "/my/challenges"),
    );
    expect(result).toBeUndefined();
  });

  it("allows authenticated user to access verify-email (not redirected)", async () => {
    mockAuthState.isAuthenticated = true;
    const result = await capturedBefore.fn!(
      makeRoute("auth/verify-email", "/verify-email"),
    );
    expect(result).toBeUndefined();
  });
});

describe("afterEach document.title guard", () => {
  it("sets document title from route meta.title", () => {
    capturedAfter.fn!(makeRoute("home", "/", "/", "", { title: "Accueil" }));
    expect(document.title).toBe("Accueil | GeoChallenge Tracker");
  });

  it("falls back to default title when no meta.title", () => {
    capturedAfter.fn!(makeRoute("home", "/", "/", "", {}));
    expect(document.title).toBe("GeoChallenge Tracker");
  });
});

describe("scrollBehavior", () => {
  it("restores saved scroll position", () => {
    const saved = { top: 200 };
    const result = capturedScroll.fn!({}, {}, saved);
    expect(result).toBe(saved);
  });

  it("scrolls to hash anchor when no saved position", () => {
    const result = capturedScroll.fn!({ hash: "#section-1" }, {}, null);
    expect(result).toEqual({ el: "#section-1" });
  });

  it("scrolls to top when no saved position and no hash", () => {
    const result = capturedScroll.fn!({ hash: "" }, {}, null);
    expect(result).toEqual({ top: 0 });
  });
});
