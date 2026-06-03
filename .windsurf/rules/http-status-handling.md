---
description: Prevent fetch wrappers from rejecting valid JSON on non-2xx HTTP status codes, and enforce URL-safe path construction
tags: [frontend, fetch, http, url-encoding, json]
---

# Rule: Safe HTTP Fetch Handling and URL Construction

## Problem

Naive `fetch` wrappers create **four** distinct failure modes:

1. **Rejection of valid JSON on non-2xx status** — Some endpoints (e.g. `GET /api/health/circuit-breakers`) return `503 Service Unavailable` with a valid JSON body indicating degraded status. A blanket `if (!response.ok) throw` silently hides this data and renders an error fallback instead of the actual data.
2. **Double-slash URLs** — Concatenating a base URL that ends with `/` and a path that starts with `/` produces `http://host//api/...`, which can fail on strict servers or proxies.
3. **Unencoded path parameters** — Interpolating user-controlled or dynamic strings into URL paths without `encodeURIComponent` allows path injection. A value like `foo/bar` or `foo?x=1` breaks the route or leaks into query parameters.
4. **Unnecessary `Content-Type` on GET requests** — Adding `Content-Type: application/json` to GET/HEAD requests with no body is unnecessary, wastes bytes, and can confuse some proxies or middleware.

## Detection

Any code that:

1. Rejects every non-2xx response before attempting to parse JSON, **or**
2. Builds URLs by concatenating base + path without normalizing slashes, **or**
3. Interpolates variables into URL paths without `encodeURIComponent`, **or**
4. Sets `Content-Type: application/json` unconditionally regardless of whether the request has a body

## Prevention

### Allow specific non-2xx statuses to return JSON

**Bad:**

```ts
async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init });
  if (!response.ok) {
    const text = await response.text(); // can throw, losing original status
    throw new Error(`HTTP ${response.status}: ${text}`);
  }
  return response.json();
}

// Caller: 503 with valid JSON is thrown away
api.circuitBreakers(); // throws when any circuit is open
```

**Good:**

```ts
interface FetchJsonInit extends RequestInit {
  /** Status codes that carry valid JSON payloads and should not throw. */
  acceptStatus?: number[];
}

async function fetchJson<T>(path: string, init?: FetchJsonInit): Promise<T> {
  const response = await fetch(url, { ...init });
  const isAccepted = init?.acceptStatus?.includes(response.status);
  if (!response.ok && !isAccepted) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(`HTTP ${response.status} ${response.statusText}: ${text}`);
  }
  return response.json();
}

// Caller: explicitly opts into 503
api.circuitBreakers = () =>
  fetchJson("/api/health/circuit-breakers", { acceptStatus: [503] });
```

### Normalize base URL trailing slash

**Bad:**

```ts
function getBaseUrl(): string {
  return window.UAR_API_URL || "http://localhost:8000";
}
const url = `${getBaseUrl()}${path}`; // double slash if base ends with /
```

**Good:**

```ts
function getBaseUrl(): string {
  const raw = window.UAR_API_URL || "http://localhost:8000";
  return raw.replace(/\/$/, "");
}
const url = `${getBaseUrl()}${path}`; // path always starts with /
```

### Encode dynamic path segments

**Bad:**

```ts
fetch(`/api/uar/recipes/${recipe.id}`); // recipe.id = "a/b" → broken route
```

**Good:**

```ts
fetch(`/api/uar/recipes/${encodeURIComponent(recipe.id)}`);
```

### Only set `Content-Type` when there is a body

**Bad:**

```ts
fetch(url, {
  headers: { "Content-Type": "application/json", ...authHeader },
});
```

**Good:**

```ts
const hasBody = init?.body != null;
fetch(url, {
  headers: {
    ...(hasBody ? { "Content-Type": "application/json" } : {}),
    ...authHeader,
    ...extraHeaders,
  },
});
```

## Checklist

- [ ] `fetchJson` wrappers accept an `acceptStatus` option for non-2xx JSON payloads
- [ ] `response.text()` is wrapped in `.catch(() => response.statusText)` so read failures don't mask the HTTP status
- [ ] Base URLs are normalized with trailing-slash removal before concatenation with absolute paths
- [ ] Every dynamic value interpolated into a URL path is passed through `encodeURIComponent`
- [ ] `Content-Type: application/json` is only added when `body != null`

> **Backend counterpart:** See `backend-http-status-check.md` for aiohttp/httpx/requests `raise_for_status()` rules.
