# TBX-Proxy API Usage Guide

A simple guide to using the TeraBox proxy API. All requests are HTTP GET requests with CORS support.

## Base URL

```
https://tbx-proxy.shakir-ansarii075.workers.dev/
```

---

## Quick Start

### 1. Get Share Metadata (Resolve)

First, extract and cache the file metadata from a TeraBox share.

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

## All Modes

| Mode / Path | Purpose | Required Params / Headers |
|------|---------|-----------------|
| `resolve` | Extract & cache metadata | `surl` |
| `lookup` | Query D1 cache (fast) | `surl` or `fid` |
| `stream` | Get M3U8 playlist | `surl` |
| `page` | Fetch TeraBox HTML page | `surl` |
| `api` | Direct API call | `jsToken`, `shorturl` |
| `segment` | Proxy video segments | `url` |
| `health` | Service health check | none |
| `/admin/*` | Admin analytics & DB inspection | `key` param or `x-admin-key` header |

---

## Mode: `resolve` ⭐ Start Here

Extracts file metadata and caches in D1.

**Required:**
- `surl` - TeraBox short URL (e.g., `abc123xyz`)

**Optional:**
- `refresh=1` - Bypass all caches, fetch fresh from TeraBox
- `raw=1` - Return full upstream data (checks D1 cache first)

**Cache Behavior:**
| Query | Cache Check | Speed |
|-------|-------------|-------|
| `?mode=resolve&surl=...` | D1 → Upstream | ~500ms first, ~10ms cached |
| `?mode=resolve&surl=...&raw=1` | D1 → Upstream | ~10ms cached |
| `?mode=resolve&surl=...&refresh=1` | None → Upstream | ~1-2s always |

**Examples:**
```bash
# First time - fetches from TeraBox and caches
curl ".../?mode=resolve&surl=abc123"
# Response: {"source": "live", "data": {...}}

# Second time - returns from D1 cache
curl ".../?mode=resolve&surl=abc123"
# Response: {"source": "d1", "data": {...}}

# Get full data from D1 cache (raw=1 cache hit returns data)
curl ".../?mode=resolve&surl=abc123&raw=1"
# Response: {"source": "d1", "data": {...}}

# Force fresh raw fetch (raw=1 cache miss/live returns upstream)
curl ".../?mode=resolve&surl=abc123&raw=1&refresh=1"
# Response: {"source": "live", "upstream": {...}}

# Force fresh fetch (normal)
curl ".../?mode=resolve&surl=abc123&refresh=1"
# Response: {"source": "live", "data": {...}}
```

---

## Mode: `lookup` 🚀 Fastest

Query D1 database directly. No upstream calls. Instant response.

**Parameters:**
- `surl` - Lookup by share ID
- `fid` - Lookup by file ID

**Examples:**
```bash
# Lookup by share
curl ".../?mode=lookup&surl=abc123"

# Lookup by file ID
curl ".../?mode=lookup&fid=511133506523791"
```

**Response:**
```json
{
  "source": "d1",
  "data": {
    "share_id": "abc123",
    "title": "...",
    "list": [{ "fs_id": "...", "server_filename": "...", "thumbs": {...} }]
  }
}
```

**Use Cases:**
- Building dashboards showing cached files
- Searching previously resolved shares
- Quick file info display without API calls

---

## Mode: `stream`

Returns M3U8 playlist for video playback. If the share metadata is not yet cached in D1, the worker will automatically resolve and cache it from upstream in the background (though calling `resolve` beforehand is recommended to reduce initial latency).

**Required:**
- `surl` - Same short URL from resolve

**Optional:**
- `type` - Video quality (default: `M3U8_AUTO_360`)
  - `M3U8_AUTO_360` - Auto quality (recommended)
  - `M3U8_AUTO_720` - Higher quality

**Example:**
```bash
curl ".../?mode=stream&surl=abc123"
```

---

## Mode: `segment`

Proxies video segments. Called automatically by M3U8 playlist.

**Security:** Only allows TeraBox domains (SSRF protected).

**Allowed Domains:**
`terabox.com`, `terabox.app`, `1024tera.com`, `1024terabox.com`, `freeterabox.com`, `teraboxcdn.com`, `dm.terabox.app`, `dm.1024tera.com`, `terasharelink.com`, `terafileshare.com`, `teraboxlink.com`, `teraboxshare.com`, `terasharefile.com`, `teraboxurl.com`

---

## Mode: `health`

```bash
# Health check
curl ".../?mode=health"
```

---

## Common Use Cases

### Stream Video in Browser

```bash
# Step 1: Get metadata and cache it
curl ".../?mode=resolve&surl=abc123"

# Step 2: Use M3U8 URL in player
M3U8_URL="https://tbx-proxy.shakir-ansarii075.workers.dev/?mode=stream&surl=abc123"

# VLC: vlc "$M3U8_URL"
# mpv: mpv "$M3U8_URL"
```

### Get File Info (Fast)

```bash
# Use lookup for cached data (instant)
curl ".../?mode=lookup&surl=abc123" | jq '.data.list[0] | {name: .server_filename, size}'
```

### Refresh Stale Data

```bash
curl ".../?mode=resolve&surl=abc123&refresh=1"
```

### Download with dlink

```bash
DLINK=$(curl -s '.../?mode=resolve&surl=abc123' | jq -r '.data.dlink')
curl -o video.mp4 "$DLINK"
```

---

## Response Sources

| Source | Meaning |
|--------|---------|
| `"source": "live"` | Fresh data from TeraBox |
| `"source": "d1"` | From D1 database (permanent) |

---

## Error Codes

Standard error responses follow this JSON schema:
```json
{
  "error": "Error message details",
  "code": "error_code_string",
  "details": "Optional additional debugging/network information",
  "required": ["optional", "param", "list"]
}
```

| HTTP Status | Error Code (`code`) | Description / Fix |
|-------------|---------------------|-------------------|
| 400 | `bad_request` | Missing or invalid parameter |
| 401 | `unauthorized` | Missing or invalid `key` / `x-admin-key` header on admin routes |
| 403 | `token_extract_failed` / `invalid_segment_url` | Failed to extract jsToken or SSRF segment URL blocked |
| 404 | `not_found` | Share or file not cached in D1 |
| 500 | `incomplete_metadata` / `db_error` / `internal_error` | Missing stream metadata or internal exceptions |
| 502 | `upstream_error` / `upstream_non_json` / `upstream_empty` | TeraBox API is down or returned invalid data |
| 503 | `d1_unavailable` | D1 database not bound/configured |
| 504 | `upstream_timeout` | The upstream TeraBox requests timed out (8s limit) |

---

## Tips

⚠️ **dlink requires cookies** — The download link won't work without valid TeraBox cookies passed in headers

✅ **Always call `resolve` first** before using `stream`

✅ **Use `lookup` for fast queries** — no upstream calls

✅ **Use `raw=1`** to get full file data with thumbnails

✅ **Use `refresh=1`** if data seems stale

✅ **M3U8 segments are auto-proxied** through the worker

✅ **CORS enabled** — works from browser JavaScript

---

## Admin Endpoints

The proxy includes path-based admin endpoints to inspect database records and analytics. All requests require authentication if `ADMIN_KEY` is configured in `wrangler.toml`. Pass the key using either:
- The `key` query parameter: `?key=YOUR_ADMIN_KEY`
- The `x-admin-key` request header: `x-admin-key: YOUR_ADMIN_KEY`

### Endpoints:

#### 1. Overview
Get overall counts of shares, files, thumbnails, and the 20 most recently updated shares.
* **Path:** `GET /admin/overview`
* **Response:** `{ "counts": { "shares": 10, "media_files": 42, "thumbnails": 168 }, "latestShares": [...] }`

#### 2. Shares List
List and search stored shares.
* **Path:** `GET /admin/shares`
* **Query Params:**
  * `q` (optional): Filter by share ID, title, or user ID (uk)
  * `sort` (optional): Sort by `updated_at`, `server_time`, or `title` (default: `updated_at`)
  * `order` (optional): `asc` or `desc` (default: `desc`)
  * `page` (optional): Page number (default: `1`)
  * `pageSize` (optional): Items per page, max 200 (default: `50`)
* **Response:** `{ "page": 1, "pageSize": 50, "total": 12, "items": [...] }`

#### 3. Share Details
Get full detail of a share, pagination of its media files, and thumbnails.
* **Path:** `GET /admin/shares/:share_id`
* **Query Params:**
  * `page` (optional): Page number of media files (default: `1`)
  * `pageSize` (optional): Files per page (default: `50`)
* **Response:** `{ "share": {...}, "files": [...], "thumbsByFsId": {...}, "page": 1, "pageSize": 50, "totalFiles": 10 }`

#### 4. Media Files List
List and filter files.
* **Path:** `GET /admin/files`
* **Query Params:**
  * `q` (optional): Search by file name or file system ID (`fs_id`)
  * `share_id` (optional): Filter files in a specific share
  * `size_min` / `size_max` (optional): Filter files by size limits (in bytes)
  * `sort` (optional): Sort by `server_mtime`, `size`, or `server_filename` (default: `server_mtime`)
  * `order` (optional): `asc` or `desc` (default: `desc`)
  * `page` / `pageSize` (optional)
* **Response:** `{ "page": 1, "pageSize": 50, "total": 10, "items": [...] }`

#### 5. File Details
Get details of a specific file and its thumbnails.
* **Path:** `GET /admin/files/:fs_id`
* **Response:** `{ "file": {...}, "thumbs": { "url1": "...", "url2": "..." } }`

#### 6. Thumbnails List
Search thumbnails.
* **Path:** `GET /admin/thumbnails`
* **Query Params:**
  * `fs_id` (optional): Filter by file system ID
  * `type` (optional): Filter by thumbnail type (`url1`, `url2`, `url3`, `icon`)
  * `page` / `pageSize` (optional)
* **Response:** `{ "page": 1, "pageSize": 50, "total": 150, "items": [...] }`

#### 7. Analytics: Processed Links
Get the count of resolved shares grouped by day.
* **Path:** `GET /admin/analytics/processed`
* **Query Params:**
  * `limit` (optional): Number of days of history, max 180 (default: `30`)
* **Response:** `{ "limit": 30, "items": [{ "day": "2026-06-08", "shares": 5 }, ...] }`

#### 8. Cache Record Entry Lookup
Retrieve a resolved record for a specific short URL from D1.
* **Path:** `GET /admin/kv/entry` (Note: queries D1 database)
* **Query Params:**
  * `surl` (required): TeraBox short URL
* **Response:** `{ "surl": "...", "data": { "name": "...", "dlink": "..." } }`

---

## Need Help?

- **Worker not deployed?** Run `npx wrangler deploy`
- **D1 not configured?** Check `wrangler.toml`
- **Getting 500 errors?** Try with `&raw=1` to see full response