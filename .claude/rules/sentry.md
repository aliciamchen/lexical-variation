---
paths:
  - "experiment/client/src/**"
---

# Sentry (Error Monitoring)

The client app reports errors to Sentry via `@sentry/react`. A Sentry MCP server is connected, so you can query production issues directly.

**Project details:**
- Organization: `lexical-variation-project`
- Project: `javascript-react`
- Region URL: `https://us.sentry.io`
- Production URL: `https://tangramcommunication.empirica.app/`

**Available MCP tools:**
- `search_issues` — list grouped issues (e.g. unresolved bugs)
- `get_issue_details` — stacktrace and event details for a specific issue ID
- `search_events` — count/aggregate errors or find individual events
- `analyze_issue_with_seer` — AI root cause analysis with code fix suggestions

**Workflow:** When investigating production bugs, check Sentry for recent issues, then cross-reference the stacktrace with the client source in `experiment/client/src/`. Reference issue IDs in commit messages (e.g. `Fixes JAVASCRIPT-REACT-1`) to auto-resolve issues on merge.

## SDK Usage Examples

These examples should be used as guidance when configuring Sentry functionality within a project.

### Error / Exception Tracking

Use `Sentry.captureException(error)` to capture an exception and log the error in Sentry.
Use this in try catch blocks or areas where exceptions are expected.

### Tracing

Spans should be created for meaningful actions within an application like button clicks, API calls, and function calls. Ensure you are creating custom spans with meaningful names and operations. Use the `Sentry.startSpan` function to create a span. Child spans can exist within a parent span.

**Custom span in component actions:**

```javascript
function TestComponent() {
  const handleTestButtonClick = () => {
    Sentry.startSpan(
      {
        op: "ui.click",
        name: "Test Button Click",
      },
      (span) => {
        const value = "some config";
        const metric = "some metric";
        span.setAttribute("config", value);
        span.setAttribute("metric", metric);
        doSomething();
      },
    );
  };

  return (
    <button type="button" onClick={handleTestButtonClick}>
      Test Sentry
    </button>
  );
}
```

**Custom span in API calls:**

```javascript
async function fetchUserData(userId) {
  return Sentry.startSpan(
    {
      op: "http.client",
      name: `GET /api/users/${userId}`,
    },
    async () => {
      const response = await fetch(`/api/users/${userId}`);
      const data = await response.json();
      return data;
    },
  );
}
```

### Logs

Where logs are used, ensure Sentry is imported using `import * as Sentry from "@sentry/react"`. Enable logging in Sentry using `Sentry.init({ enableLogs: true })`. Reference the logger using `const { logger } = Sentry`. Sentry offers a consoleLoggingIntegration that can be used to log specific console error types automatically without instrumenting the individual logger calls.

**Configuration:**

```javascript
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: "https://82d1223301f5ea7d0c6d07f9935aeabd@o4510902672359424.ingest.us.sentry.io/4510908813541376",
  enableLogs: true,
  integrations: [
    // optionally send console.log, console.warn, and console.error calls as logs
    Sentry.consoleLoggingIntegration({ levels: ["log", "warn", "error"] }),
  ],
});
```

**Logger examples:**

`logger.fmt` is a template literal function that should be used to bring variables into the structured logs.

```javascript
logger.trace("Starting database connection", { database: "users" });
logger.debug(logger.fmt`Cache miss for user: ${userId}`);
logger.info("Updated profile", { profileId: 345 });
logger.warn("Rate limit reached for endpoint", { endpoint: "/api/results/", isEnterprise: false });
logger.error("Failed to process payment", { orderId: "order_123", amount: 99.99 });
logger.fatal("Database connection pool exhausted", { database: "users", activeConnections: 100 });
```
