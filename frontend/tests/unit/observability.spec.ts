import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { App } from "vue";

vi.mock("@sentry/vue", () => ({
  init: vi.fn<(options: unknown) => void>(),
  vueIntegration: vi.fn<() => { name: string }>(() => ({
    name: "vue-integration",
  })),
}));

import * as Sentry from "@sentry/vue";
import { initErrorTracking } from "@/observability";

const DSN = "https://public@o0.ingest.de.sentry.io/0";

describe("initErrorTracking", () => {
  const app = {} as App;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each(["", "   "])("does not initialize Sentry when DSN is %j", (dsn) => {
    vi.stubEnv("VITE_SENTRY_DSN", dsn);

    initErrorTracking(app);

    expect(Sentry.init).not.toHaveBeenCalled();
  });

  it("initializes Sentry with the configured DSN and environment", () => {
    vi.stubEnv("VITE_SENTRY_DSN", ` ${DSN} `);
    vi.stubEnv("VITE_SENTRY_ENVIRONMENT", "production");

    initErrorTracking(app);

    expect(Sentry.init).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        app,
        dsn: DSN,
        environment: "production",
        integrations: [{ name: "vue-integration" }],
        tracesSampleRate: 0,
      }),
    );
  });

  it("defaults to development when environment is absent", () => {
    vi.stubEnv("VITE_SENTRY_DSN", DSN);
    vi.stubEnv("VITE_SENTRY_ENVIRONMENT", "");

    initErrorTracking(app);

    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({ environment: "development" }),
    );
  });

  it("disables request and user data collection", () => {
    vi.stubEnv("VITE_SENTRY_DSN", DSN);

    initErrorTracking(app);

    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dataCollection: expect.objectContaining({
          userInfo: false,
          cookies: false,
          httpHeaders: { request: false, response: false },
          httpBodies: [],
          urlQueryParams: false,
          stackFrameVariables: false,
          frameContextLines: 0,
        }),
      }),
    );
  });
});
