---
description: Testing rules for validating HTTP fetch patterns, URL construction, and status code handling
tags: [testing, fetch, http, url-encoding, regression]
---

# Rule: Test Fetch Patterns and URL Construction

## Purpose

Ensure all fetch/API calls are tested for:

1. Correct URL encoding of dynamic path parameters
2. Graceful handling of non-2xx JSON responses (e.g. 503)
3. Proper base URL normalization (no double slashes)
4. Conditional Content-Type headers

## Test Patterns

### 1. URL Encoding Tests

Every component that constructs URLs with dynamic path parameters MUST have a test verifying encoding:

```ts
// Component under test
function buildUrl(id: string): string {
  return `/api/uar/items/${encodeURIComponent(id)}`
}

// Test
it('url-encodes path parameters', () => {
  expect(buildUrl('a/b')).toBe('/api/uar/items/a%2Fb')
  expect(buildUrl('a?x=1')).toBe('/api/uar/items/a%3Fx%3D1')
  expect(buildUrl('a#b')).toBe('/api/uar/items/a%23b')
})
```

### 2. Non-2xx JSON Response Tests

Any endpoint that can return valid JSON with non-2xx status MUST be tested:

```ts
it('renders data when backend returns 503 degraded', async () => {
  vi.mocked(api.circuitBreakers).mockResolvedValue({
    status: 'degraded',
    circuits: { 'anthropic': { state: 'open', failures: 5 } },
  })

  render(<TopologyGraph />)

  await waitFor(() => {
    expect(screen.getByText('anthropic')).toBeInTheDocument()
    expect(screen.getByText('1 open')).toBeInTheDocument()
  })
})
```

### 3. Base URL Normalization Tests

URL construction helpers MUST be tested for trailing slash handling:

```ts
it('normalizes trailing slashes', () => {
  expect(getBaseUrl('http://host:8000/')).toBe('http://host:8000')
  expect(getBaseUrl('http://host:8000')).toBe('http://host:8000')
})

it('prevents double slashes', () => {
  const base = getBaseUrl('http://host:8000/')
  expect(`${base}/api/health`).toBe('http://host:8000/api/health')
})
```

### 4. Content-Type Header Tests

Verify Content-Type is only present when body exists:

```ts
it('omits Content-Type for GET requests', async () => {
  const fetchSpy = vi.spyOn(global, 'fetch')
  await api.listRuns()
  const headers = fetchSpy.mock.calls[0][1]?.headers as Record<string, string>
  expect(headers).not.toHaveProperty('Content-Type')
})

it('includes Content-Type for POST with body', async () => {
  const fetchSpy = vi.spyOn(global, 'fetch')
  await api.pingSkill('echo')
  const headers = fetchSpy.mock.calls[0][1]?.headers as Record<string, string>
  expect(headers['Content-Type']).toBe('application/json')
})
```

## Checklist for New Components

- [ ] All dynamic values in URL paths use `encodeURIComponent`
- [ ] Base URLs are normalized (trailing slash removed) before concatenation
- [ ] Non-2xx JSON responses (503, etc.) are handled gracefully
- [ ] Content-Type is only set when request body is present
- [ ] Mock responses cover both success and degraded/error states
- [ ] Tests verify no double slashes in constructed URLs

## Regression Prevention

When reviewing code:

1. Search for `fetch(`
