import type { App } from "vue";
import * as Sentry from "@sentry/vue";
import type { ErrorEvent } from "@sentry/vue";

/**
 * Safety net on top of `dataCollection`: drops request data and breadcrumbs, and keeps
 * only the path of the page URL (page URLs can carry tokens, e.g. `/verify-email?token=`).
 * @param event - Event about to be sent.
 * @returns The same event, scrubbed.
 */
export function scrubEvent(event: ErrorEvent): ErrorEvent {
  if (event.request) {
    delete event.request.data;
    delete event.request.headers;
    delete event.request.cookies;
    delete event.request.query_string;
    if (event.request.url) {
      event.request.url = event.request.url.split(/[?#]/)[0];
    }
  }
  delete event.breadcrumbs;
  return event;
}

/**
 * Initializes Sentry error tracking when `VITE_SENTRY_DSN` is set at build time.
 * Sends stack traces only: no user, cookie, header, body, query string, prop or breadcrumb.
 * Events go through the backend relay at `/api/<hash of the DSN>` (see
 * `backend/app/api/routes/sentry_tunnel.py`), so ad-blockers don't drop them.
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
    integrations: [Sentry.vueIntegration({ attachProps: false })],
    tunnel: { basePath: "/api" },
    tracesSampleRate: 0,
    beforeSend: scrubEvent,
    beforeBreadcrumb: () => null,
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
      mcp: {
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
