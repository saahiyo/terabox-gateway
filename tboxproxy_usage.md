# TBX-Proxy API Usage Guide

A simple guide to using the TeraBox proxy API. All requests are HTTP GET requests.

## Base URL

```
https://tbx-proxy.shakir-ansarii075.workers.dev/
```

---

## Quick Start

### 1. Get Share Metadata (Resolve)

First, you need to extract and cache the file metadata from a TeraBox share.

```bash
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=resolve&surl=YOUR_SHORT_URL"
```

**Response:**
```json
{
  "source": "live",
  "data": {
    "name": "video.mp4",
    "size": 168800237,
    "thumb": "https://...",
    "dlink": "https://...",
    "fid": "511133506523791",
    "uk": "4401146149342",
    "shareid": "10524102871"
  }
}
```

---

### 2. Stream the Video (Get M3U8)

Once resolved, get the M3U8 playlist URL for streaming.

```bash
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=stream&surl=YOUR_SHORT_URL"
```

**Response:** M3U8 playlist content (can be used with VLC, HLS.js, etc.)

---

### 3. Fetch Share Page

Get the TeraBox share page HTML.

```bash
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=page&surl=YOUR_SHORT_URL"
```

---

## All Modes Explained

### Mode: `resolve` ⭐ Start Here
Extracts file metadata and caches it for 24+ hours.

**Required:**
- `surl` - TeraBox short URL (e.g., `abc123xyz`)

**Optional:**
- `refresh=1` - Bypass cache and fetch fresh data
- `raw=1` - Return raw upstream response (debugging)

**Example:**
```bash
# Get and cache metadata
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=resolve&surl=abc123"

# Force refresh from TeraBox
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=resolve&surl=abc123&refresh=1"
```

**Success Response (200):**
```json
{
  "source": "live",
  "data": {
    "name": "filename.mp4",
    "size": 168800237,
    "thumb": "https://...",
    "dlink": "https://...",
    "fid": "...",
    "uk": "...",
    "shareid": "...",
    "stored_at": 1609459200
  }
}
```

---

### Mode: `stream`
Returns M3U8 playlist for video playback. **Requires calling `resolve` first.**

**Required:**
- `surl` - Same short URL from resolve

**Optional:**
- `type` - Video quality (default: `M3U8_AUTO_360`)
  - `M3U8_AUTO_360` - Auto quality (recommended)
  - `M3U8_AUTO_720`
  - Other quality options available

**Example:**
```bash
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=stream&surl=abc123"
```

**Response:** M3U8 playlist file (text/vnd.apple.mpegurl)

---

### Mode: `page`
Fetches the TeraBox share page as HTML.

**Required:**
- `surl` - Short URL

**Example:**
```bash
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=page&surl=abc123"
```

**Response:** HTML page content

---

### Mode: `api`
Direct API call to TeraBox (advanced).

**Required:**
- `jsToken` - JavaScript token (extracted from page)
- `shorturl` - Short URL

**Example:**
```bash
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=api&jsToken=TOKEN123&shorturl=abc123"
```

**Response:** Raw JSON from TeraBox API

---

### Mode: `segment`
Proxies video segments (internal use, called automatically by M3U8 playlist).

**Required:**
- `url` - Full segment URL

**Example:**
```bash
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=segment&url=https://..."
```

---

## Common Use Cases

### Use Case 1: Stream Video in Browser

```bash
# Step 1: Get metadata and cache it
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=resolve&surl=abc123"

# Step 2: Get M3U8 URL
M3U8_URL="https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=stream&surl=abc123"

# Step 3: Use in video player
# VLC: vlc "$M3U8_URL"
# HLS.js: video.src = "$M3U8_URL"
# mpv: mpv "$M3U8_URL"
```

### Use Case 2: Get File Info

```bash
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=resolve&surl=abc123" \
  | jq '.data | {name, size, thumb}'
```

### Use Case 3: Refresh Cached Data

If the TeraBox link was updated:

```bash
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=resolve&surl=abc123&refresh=1"
```

### Use Case 4: Download with Signature

After resolving, use the `dlink` URL directly with a downloader:

```bash
curl -o video.mp4 "$(curl -s 'https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=resolve&surl=abc123' | jq -r '.data.dlink')"
```

---

## Error Codes & Fixes

| Code | Error | Fix |
|------|-------|-----|
| 400 | Missing parameter | Check required params (surl, jsToken, etc.) |
| 403 | Failed to extract token | Share may be private or link expired |
| 404 | Share not in cache | Call `mode=resolve` first |
| 500 | Incomplete metadata | Try `mode=resolve&refresh=1` |
| 502 | Bad upstream response | TeraBox API may be down |

---

## Response Format

All successful responses are JSON:

```json
{
  "source": "live|kv",
  "data": { ... }
}
```

Error responses:

```json
{
  "error": "Error message",
  "required": ["param1", "param2"]
}
```

---

## Tips & Tricks

✅ **Always call `resolve` first** before using `stream`

✅ **Cache is automatic** — metadata is cached for ~24 hours

✅ **Use `refresh=1`** if data seems stale

✅ **M3U8 playlists are rewritten** — segments are automatically proxied through the worker

✅ **Thumbnails available** in resolve response (`data.thumb`)

---

## Testing with cURL

```bash
# Test resolve
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=resolve&surl=abc123" | jq

# Test stream (get M3U8)
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=stream&surl=abc123"

# Test missing parameter
curl "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=api"

# Pretty-print JSON
curl -s "https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=resolve&surl=abc123" | jq .
```

---

## Need Help?

- **Worker not deployed?** Run `wrangler deploy`
- **KV not configured?** Check `wrangler.toml` has correct KV namespace
- **Getting 500 errors?** Try with `&raw=1` to see upstream response
- **Link expired?** Use `&refresh=1` to re-fetch from TeraBox
