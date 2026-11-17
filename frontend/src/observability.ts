import type { App } from "vue";
import * as Sentry from "@sentry/vue";

/**
 * Initializes Sentry error tracking when `VITE_SENTRY_DSN` is set at build time.
 * Sends stack traces only: no user, cookie, header, body or query string data.
 * @param app - Vue application instance, so Vue errors are reported too.
 */
export function initErrorTracking(app: App): void {
  const sentryDsn = import.meta.env.VITE_SENTRY_DSN?.trim();

  if (!sentryDsn) {
    return;
  }

  Sentry.init({
    app,
    dsn: sentryDsn,
    environment: import.meta.env.VITE_SENTRY_ENVIRONMENT || "development",
    integrations: [Sentry.vueIntegration()],
    tracesSampleRate: 0,
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: {
        request: false,
        response: false,
      },
      httpBodies: [],
      urlQueryParams: false,
      graphQL: {
        document: false,
        variables: false,
      },
      genAI: {
        inputs: false,
        outputs: false,
      },
      databaseQueryData: false,
      queues: false,
      stackFrameVariables: false,
      frameContextLines: 0,
    },
  });
}
