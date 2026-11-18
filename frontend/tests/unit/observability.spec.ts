import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { App } from "vue";
import type { ErrorEvent } from "@sentry/vue";

vi.mock("@sentry/vue", () => ({
  init: vi.fn<(options: unknown) => void>(),
  vueIntegration: vi.fn<(options: unknown) => { name: string }>(() => ({
    name: "vue-integration",
  })),
}));

import * as Sentry from "@sentry/vue";
import { initErrorTracking, scrubEvent } from "@/observability";

const DSN = "https://public@o0.ingest.de.sentry.io/0";

type InitOptions = {
  beforeBreadcrumb: (crumb: unknown) => unknown;
  beforeSend: unknown;
};

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

  it("initializes Sentry with the configured DSN, environment and relay", () => {
    vi.stubEnv("VITE_SENTRY_DSN", ` ${DSN} `);
    vi.stubEnv("VITE_SENTRY_ENVIRONMENT", "production");

    initErrorTracking(app);

    expect(Sentry.init).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        app,
        dsn: DSN,
        environment: "production",
        integrations: [{ name: "vue-integration" }],
        tunnel: { basePath: "/api" },
        tracesSampleRate: 0,
        beforeSend: scrubEvent,
      }),
    );
    expect(Sentry.vueIntegration).toHaveBeenCalledExactlyOnceWith({
      attachProps: false,
    });
  });

  it("defaults to development when environment is absent", () => {
    vi.stubEnv("VITE_SENTRY_DSN", DSN);
    vi.stubEnv("VITE_SENTRY_ENVIRONMENT", "");

    initErrorTracking(app);

    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({ environment: "development" }),
    );
  });

  it("drops every breadcrumb", () => {
    vi.stubEnv("VITE_SENTRY_DSN", DSN);

    initErrorTracking(app);

    const options = vi.mocked(Sentry.init).mock.calls[0][0] as InitOptions;
    expect(options.beforeBreadcrumb({ category: "console" })).toBeNull();
  });

  it("disables request and user data collection", () => {
    vi.stubEnv("VITE_SENTRY_DSN", DSN);

    initErrorTracking(app);

    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dataCollection: {
          userInfo: false,
          cookies: false,
          httpHeaders: { request: false, response: false },
          httpBodies: [],
          urlQueryParams: false,
          graphQL: { document: false, variables: false },
          genAI: { inputs: false, outputs: false },
          mcp: { inputs: false, outputs: false },
          databaseQueryData: false,
          queues: false,
          stackFrameVariables: false,
          frameContextLines: 0,
        },
      }),
    );
  });
});

describe("scrubEvent", () => {
  it("drops request data and breadcrumbs, keeps the URL path", () => {
    const event = {
      type: undefined,
      message: "boom",
      request: {
        url: "https://gct.test/verify-email?token=secret#frag",
        data: { password: "secret" },
        headers: { Authorization: "Bearer secret" },
        cookies: { session: "secret" },
        query_string: "token=secret",
      },
      breadcrumbs: [{ message: "secret" }],
    } as ErrorEvent;

    expect(scrubEvent(event)).toEqual({
      type: undefined,
      message: "boom",
      request: { url: "https://gct.test/verify-email" },
    });
  });

  it("keeps an event without request untouched", () => {
    const event = { type: undefined, message: "boom" } as ErrorEvent;

    expect(scrubEvent(event)).toEqual({ type: undefined, message: "boom" });
  });
});
