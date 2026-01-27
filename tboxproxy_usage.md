# TeraBox Unified Cloudflare Worker API

A single Cloudflare Worker endpoint to proxy **TeraBox share pages and APIs**, with optional cookie forwarding and automatic `jsToken` resolution.

---

## Base URL

```text
https://tbx-proxy.shakir-ansarii075.workers.dev/
```

All behavior is controlled using the `mode` query parameter.

---

## Supported Modes

### 1. `mode=resolve` (Recommended)

Automatically:
- Fetches the TeraBox share page
- Extracts `jsToken`
- Calls the TeraBox share API
- Returns JSON metadata

**Endpoint**
```text
/?mode=resolve&surl=<SHORT_URL_ID>
```

**Example**
```text
/?mode=resolve&surl=abc123
```

**Notes**
- Cookies are forwarded **only if provided by the client**
- Required for private or logged-in shares
- `jsToken` is short-lived; resolve mode is safest

---

### 2. `mode=page` (HTML Proxy)

Returns the raw HTML of the TeraBox share page.

**Endpoint**
```text
/?mode=page&surl=<SHORT_URL_ID>
```

**Example**
```text
/?mode=page&surl=abc123
```

**Use cases**
- Debugging
- Manual inspection
- Client-side parsing

---

### 3. `mode=api` (Manual API Access)

Directly proxies the TeraBox share API when `jsToken` is already available.

**Endpoint**
```text
/?mode=api&jsToken=<JS_TOKEN>&shorturl=<SHORT_URL_ID>
```

**Optional parameters**
- `root` (default: `1`)
- `dplogid`

**Example**
```text
/?mode=api&jsToken=XYZ&shorturl=abc123
```

---

## Cookie Handling

- If the client sends cookies, they are forwarded upstream
- If no cookies are provided, requests proceed without cookies
- No server-side or hard-coded cookies are used

**Cookies are required for**
- Private shares
- Logged-in user content
- Preventing empty or restricted API responses

---

## Error Responses

Common error formats:

```json
{ "error": "Missing surl" }
```

```json
{ "error": "Failed to extract jsToken (cookie may be required)" }
```

```json
{
  "error": "Invalid or missing mode",
  "allowed": ["page", "api", "resolve"]
}
```

---

## Recommended Usage Flow

```text
Client
  ↓
/?mode=resolve&surl=XXXX
  ↓
Worker fetches HTML
  ↓
Extracts jsToken
  ↓
Calls TeraBox API
  ↓
Returns JSON
```

---

## Best Practices

- Prefer `mode=resolve` for most integrations
- Always pass cookies for private or restricted shares
- Treat `jsToken` as temporary and non-cacheable
- Avoid exposing cookies in client-side applications

---

## Common Use Cases

- Telegram bots
- Download link resolvers
- File indexers
- Backend APIs
- Cloudflare Workers with KV caching

---

## License

Use responsibly. This project is intended for educational and interoperability purposes.
