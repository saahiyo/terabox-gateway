# TeraBox Unified Cloudflare Worker API

A single **Cloudflare Worker** that proxies **TeraBox share pages, APIs, and HLS streaming**, with:

- Automatic `jsToken` extraction
- Optional cookie forwarding
- Playable **HLS (M3U8) streaming**
- Segment (`.ts / .m4s`) proxying
- Browser, mobile, and VLC compatibility

---

## Base URL

```text
https://<your-worker>.workers.dev/
```

All behavior is controlled using the `mode` query parameter.

---

## Supported Modes Overview

| Mode        | Purpose |
|------------|--------|
| `resolve`  | Auto extract `jsToken` + fetch share API (recommended) |
| `page`     | Proxy raw share HTML |
| `api`      | Manual share API proxy |
| `stream`   | Fetch + rewrite M3U8 playlist |
| `segment`  | Proxy media segments (`.ts`, `.m4s`) |

---

## 1️⃣ mode=resolve (Recommended)

Automatically:
- Fetches the TeraBox share page
- Extracts `jsToken`
- Calls the share API
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

## 2️⃣ mode=page (HTML Proxy)

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
- Token investigation

---

## 3️⃣ mode=api (Manual Share API)

Directly proxies the TeraBox share API when `jsToken` is already known.

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

## 4️⃣ mode=stream (HLS Playlist Proxy)

Fetches the **TeraBox M3U8 playlist**, then **rewrites all segment URLs**
so that **every media request goes through the Worker**.

**Endpoint**
```text
/?mode=stream&uk=...&shareid=...&fid=...&jsToken=...&type=M3U8_AUTO_360
```

**What it does**
- Proxies `/share/streaming`
- Rewrites segment URLs to `mode=segment`
- Returns a **playable M3U8**

**Use directly in players**
- hls.js
- video.js
- VLC
- Android / iOS players

---

## 5️⃣ mode=segment (Media Segment Proxy)

Proxies individual video segments (`.ts`, `.m4s`).

This mode is **automatically used** by rewritten playlists — you do not need
to call it manually.

**Endpoint**
```text
/?mode=segment&url=<ENCODED_TS_OR_M4S_URL>
```

**Purpose**
- Preserves cookies & headers
- Avoids CORS issues
- Prevents direct CDN blocking

---

## Cookie Handling

- If the client sends cookies → they are forwarded upstream
- If no cookies are provided → request proceeds without cookies
- No hard-coded or server-side cookies are used

**Cookies are required for**
- Private shares
- Logged-in content
- Avoiding empty or restricted responses

---

## Error Responses

```json
{ "error": "Missing surl" }
```

```json
{ "error": "Failed to extract jsToken (cookie may be required)" }
```

```json
{
  "error": "Invalid or missing mode",
  "allowed": ["page", "api", "resolve", "stream", "segment"]
}
```

---

## Recommended Usage Flow (Streaming)

```text
Player
  ↓
/?mode=stream
  ↓
Worker rewrites M3U8
  ↓
Player requests segments
  ↓
/?mode=segment
  ↓
TeraBox CDN
```

---

## Best Practices

- Use `mode=resolve` for metadata access
- Use `mode=stream` for video playback
- Always forward cookies for private content
- Do not cache `jsToken` client-side
- Treat stream URLs as temporary

---

## Common Use Cases

- Telegram / Discord bots
- Web-based HLS players
- Download link resolvers
- File browsers
- Backend-only streaming APIs
- Cloudflare Workers + KV caching

---

## Legal / Disclaimer

This project is for **educational and interoperability purposes only**.  
You are responsible for complying with TeraBox terms of service and
applicable laws.
