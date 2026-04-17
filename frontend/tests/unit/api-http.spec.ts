import { describe, it, expect, vi, beforeEach } from "vitest";

// Capture interceptors registered when the module loads
const capturedReq = vi.hoisted(() => ({
  fn: null as ((cfg: unknown) => unknown) | null,
}));
const capturedRes = vi.hoisted(() => ({
  ok: null as ((res: unknown) => unknown) | null,
  err: null as ((err: unknown) => unknown) | null,
}));

// The axios instance itself must be callable (used as api(config) on retry)
const mockAxiosCall = vi.hoisted(() => vi.fn());

// Shared auth state — mutated between tests
const mockAuthState = vi.hoisted(() => ({
  accessToken: "tok123",
  logout: vi.fn(),
  refresh: vi.fn(),
}));

const mockToastError = vi.hoisted(() => vi.fn());
const mockRouterPush = vi.hoisted(() => vi.fn());

vi.mock("@/store/auth", () => ({
  useAuthStore: () => mockAuthState,
}));

vi.mock("vue-sonner", () => ({ toast: { error: mockToastError } }));

vi.mock("@/router", () => ({
  default: {
    currentRoute: { value: { name: "home" } },
    push: mockRouterPush,
  },
}));

vi.mock("axios", () => {
  class AxiosHeaders {
    _h: Record<string, string>;
    constructor(init?: Record<string, string>) {
      this._h = { ...(init ?? {}) };
    }
    set(k: string, v: string) {
      this._h[k] = v;
    }
    get(k: string) {
      return this._h[k];
    }
  }

  const instance = Object.assign(mockAxiosCall, {
    interceptors: {
      request: {
        use: vi.fn((fn: (cfg: unknown) => unknown) => {
          capturedReq.fn = fn;
        }),
      },
      response: {
        use: vi.fn(
          (ok: (res: unknown) => unknown, err: (e: unknown) => unknown) => {
            capturedRes.ok = ok;
            capturedRes.err = err;
          },
        ),
      },
    },
  });

  return {
    default: { create: vi.fn(() => instance) },
    AxiosHeaders,
    AxiosError: class AxiosError extends Error {
      response?: { status: number };
      config?: Record<string, unknown>;
    },
  };
});

// Import triggers interceptor registration on the mock instance
import "@/api/http";
import axios from "axios";

// ── paramsSerializer ─────────────────────────────────────────────────────────

type Serializer = (params: Record<string, unknown>) => string;

let paramsSerializer: Serializer;

beforeAll(() => {
  const createMock = axios.create as ReturnType<typeof vi.fn>;
  const opts = createMock.mock.calls[0]?.[0] as {
    paramsSerializer?: Serializer;
  };
  paramsSerializer = opts?.paramsSerializer as Serializer;
});

describe("paramsSerializer", () => {
  it("serializes scalar values", () => {
    expect(paramsSerializer({ country: "FR", level: 1 })).toBe(
      "country=FR&level=1",
    );
  });

  it("repeats array values without bracket notation", () => {
    expect(paramsSerializer({ type: ["traditional", "multi"] })).toBe(
      "type=traditional&type=multi",
    );
  });

  it("omits null and undefined values", () => {
    expect(paramsSerializer({ a: null, b: undefined, c: "keep" })).toBe(
      "c=keep",
    );
  });
});

// ── helpers ──────────────────────────────────────────────────────────────────

const makeConfig = (overrides: Record<string, unknown> = {}) => ({
  headers: {} as Record<string, unknown>,
  url: "/some/endpoint",
  ...overrides,
});

const make401 = (configOverrides: Record<string, unknown> = {}) => ({
  response: { status: 401 },
  config: makeConfig(configOverrides),
});

beforeEach(() => {
  mockAuthState.accessToken = "tok123";
  sessionStorage.clear();
  vi.clearAllMocks();
});

// ── request interceptor ───────────────────────────────────────────────────────

describe("request interceptor", () => {
  it("adds Authorization header when accessToken is set", () => {
    const cfg = makeConfig();
    capturedReq.fn!(cfg);
    expect(cfg.headers.get("Authorization")).toBe("Bearer tok123");
  });

  it("restores token from sessionStorage when store has no token", () => {
    mockAuthState.accessToken = "";
    sessionStorage.setItem("access_token", "cached-tok");
    const cfg = makeConfig();
    capturedReq.fn!(cfg);
    expect(mockAuthState.accessToken).toBe("cached-tok");
    expect(cfg.headers.get("Authorization")).toBe("Bearer cached-tok");
  });

  it("leaves header unset when no token in store or sessionStorage", () => {
    mockAuthState.accessToken = "";
    const cfg = makeConfig();
    capturedReq.fn!(cfg);
    // headers remains a plain object — no Authorization set
    expect(cfg.headers.Authorization).toBeUndefined();
  });
});

// ── response interceptor — success ────────────────────────────────────────────

describe("response interceptor — success passthrough", () => {
  it("returns the response unchanged", async () => {
    const res = { status: 200, data: {} };
    const result = await capturedRes.ok!(res);
    expect(result).toBe(res);
  });
});

// ── response interceptor — non-401 errors ────────────────────────────────────

describe("response interceptor — non-401 errors", () => {
  it("rejects non-401 errors unchanged", async () => {
    const err = { response: { status: 500 }, config: makeConfig() };
    await expect(capturedRes.err!(err)).rejects.toBe(err);
  });

  it("rejects when config is undefined", async () => {
    const err = { response: { status: 401 }, config: undefined };
    await expect(capturedRes.err!(err)).rejects.toBe(err);
  });
});

// ── response interceptor — 401 on refresh endpoint ───────────────────────────

describe("response interceptor — 401 on /auth/refresh", () => {
  it("calls logout, shows toast, and rejects", async () => {
    const err = make401({ url: "/auth/refresh" });
    await expect(capturedRes.err!(err)).rejects.toBeDefined();
    expect(mockAuthState.logout).toHaveBeenCalled();
    expect(mockToastError).toHaveBeenCalled();
  });
});

// ── response interceptor — 401 token refresh flow ────────────────────────────

describe("response interceptor — 401 refresh and retry", () => {
  it("refreshes token, updates header, and retries original request", async () => {
    mockAuthState.refresh.mockResolvedValueOnce(undefined);
    mockAxiosCall.mockResolvedValueOnce({ data: "retried" });
    const err = make401();

    const result = await capturedRes.err!(err);

    expect(mockAuthState.refresh).toHaveBeenCalledOnce();
    expect(mockAxiosCall).toHaveBeenCalledWith(err.config);
    expect(result).toEqual({ data: "retried" });
  });

  it("calls handleSessionExpired when refresh fails", async () => {
    mockAuthState.refresh.mockRejectedValueOnce(new Error("refresh fail"));
    const err = make401();

    await expect(capturedRes.err!(err)).rejects.toBeDefined();
    expect(mockAuthState.logout).toHaveBeenCalled();
    expect(mockToastError).toHaveBeenCalled();
  });

  it("does not retry when _retry flag is already set", async () => {
    const err = make401({ _retry: true });
    await expect(capturedRes.err!(err)).rejects.toBeDefined();
    expect(mockAuthState.refresh).not.toHaveBeenCalled();
  });
});
