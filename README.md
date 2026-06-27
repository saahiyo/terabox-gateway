# TeraBox Gateway API

Fast Python gateway for extracting metadata, thumbnails and direct download links from Terabox share URLs.

[![GitHub Stars](https://img.shields.io/github/stars/saahiyo/terabox-gateway?style=for-the-badge&color=gold)](https://github.com/saahiyo/terabox-gateway/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/saahiyo/terabox-gateway?style=for-the-badge&color=blue)](https://github.com/saahiyo/terabox-gateway/network/members)
[![License](https://img.shields.io/github/license/saahiyo/terabox-gateway?style=for-the-badge&color=green)](https://github.com/saahiyo/terabox-gateway/blob/main/LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge&logo=python)](https://github.com/saahiyo/terabox-gateway)
[![Deploy on Vercel](https://img.shields.io/badge/Deploy-Vercel-black?style=for-the-badge&logo=vercel)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fsaahiyo%2Fterabox-gateway&env=COOKIE_JSON)

![design](https://github.com/user-attachments/assets/8129a66c-99b3-4487-9859-8ec7999a6475)


This project provides:
- **Interactive Swagger Playground** at `/docs` for testing endpoints directly in the browser
- **Web API** with endpoints for listing files and retrieving direct links
- **Unified Cloudflare Worker Proxy** for optimized TeraBox API access
- **Vercel-ready deployment** configuration
- **Flexible cookie authentication** with support for simple string or JSON formats

The API uses Flask 3.x native async support with `aiohttp` for asynchronous requests and leverages a unified Cloudflare Worker proxy with mode-based operations for efficient TeraBox API interaction.

---

## Features

- **Web API Endpoints**:
  - `GET /docs`: Interactive Swagger UI documentation playground (API playground)
  - `GET /swagger.json`: OpenAPI 3.0.0 schema specification
  - `GET /api`: Unified endpoint - file listing, direct links (`?direct=true`), and proxy modes (resolve, lookup, stream, page, api, segment, health)
  - `GET /admin/*`: Path-based admin endpoints to inspect database records and analytics (overview, shares, files, thumbnails, kv/entry)
  - `GET /health`: Simple health check endpoint
  - `GET /`: API information and status

- **Flexible Cookie Configuration**:
  - Simple string format: Just paste your `ndus` token
  - Full JSON format: Supports multiple cookie fields
  - Environment variable or file-based configuration

- **Rate Limiting**:
  - Per-IP sliding-window rate limiter
  - Configurable limits via environment variables
  - Returns `429 Too Many Requests` with `Retry-After` header

- **Response Caching**:
  - In-memory LRU cache with TTL expiration
  - Reduces redundant upstream requests on repeated lookups
  - Configurable TTL and max cache size

- **Production Ready**:
  - CORS enabled for browser clients
  - Vercel deployment configuration included
  - Error handling with detailed logging

---

## Directory Structure

```
terabox-gateway/
├── api.py                # Main Flask application and API routes
├── config.py             # Configuration and constants (proxy URLs, headers)
├── terabox_client.py     # TeraBox API client with unified proxy integration
├── utils.py              # Utility functions (validation, formatting)
├── rate_limiter.py       # Per-IP sliding-window rate limiter
├── cache.py              # In-memory LRU cache with TTL expiration
├── main.py               # Entry point for running Flask locally
├── .env                  # Environment variables (not tracked in git)
├── .env.example          # Example environment configuration
├── requirements.txt      # Python dependencies
├── vercel.json           # Vercel deployment configuration
├── tboxproxy_usage.md    # Unified proxy API documentation
├── .gitignore            # Git ignore file
├── LICENSE               # MIT License
├── README.md             # This file
└── endpoints/            # Reserved for future route modularization
```

---

## Requirements

- **Python 3.10+**
- **Dependencies**:
  - `Flask[async]>=3.1,<4`
  - `Werkzeug>=3.1,<4`
  - `aiohttp>=3.8,<4`

### Installation

Install the required packages using pip:

```bash
pip install -r requirements.txt
```

---

## Quick Start

### 1. Configure Cookies

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Add your TeraBox `ndus` cookie token to `.env`:

**Option 1: Simple String Format (Recommended)**
```env
COOKIE_JSON=YdPCtvYteHui3XC6demNk-M2HgRzVrnh0txZQG6X
```

**Option 2: Full JSON Format**
```env
COOKIE_JSON={"ndus": "YdPCtvYteHui3XC6demNk-M2HgRzVrnh0txZQG6X", "other": "value"}
```

The API automatically detects the format and handles it accordingly.

### 2. Run the API Locally

Execute the `main.py` script:

```bash
python main.py
```

The server will start at:
- `http://localhost:5000`
- `http://0.0.0.0:5000` (accessible from network)

---

## Getting Your TeraBox Cookies

The API requires a valid `ndus` cookie to authenticate with TeraBox:

1. Log in to [terabox.com](https://www.terabox.com) or [1024terabox.com](https://1024terabox.com)
2. Open your browser's Developer Tools (press `F12`)
3. Go to the **Application** or **Storage** tab
4. Navigate to **Cookies** → Select the TeraBox domain
5. Find the cookie named `ndus` and copy its **Value**
6. Paste the value into your `.env` file as shown above

**Note**: Cookies expire periodically. If you start getting authentication errors, refresh your cookies.

---

## API Usage

### Endpoints

#### `GET /` - API Information
Returns metadata about the API, available endpoints, and status.

```bash
curl http://localhost:5000/
```

#### `GET /health` - Health Check
Simple health check endpoint that returns the current status.

```bash
curl http://localhost:5000/health
```


#### `GET /docs` - Interactive Swagger UI Playground
An interactive developer playground to browse endpoints and execute requests directly from the browser.

Access in browser at: `http://localhost:5000/docs`

#### `GET /swagger.json` - OpenAPI Specification
Exposes the OpenAPI 3.0.0 JSON schema defining the entire API.

```bash
curl http://localhost:5000/swagger.json
```


#### `GET /api` - Unified Endpoint (File Listing + Direct Links + Proxy Modes)

The `/api` endpoint handles **all use cases** in one place:

**Pattern 1: File Listing (Metadata Only)**
Retrieves file metadata for a TeraBox share link.

```bash
curl "http://localhost:5000/api?url=https://1024terabox.com/s/1LNr3tyl5pI5KUM8BecGtyQ"
```

**Pattern 2: Direct Download Links**
Fetch metadata **and** resolved direct download links in one call.

```bash
curl "http://localhost:5000/api?url=https://teraboxshare.com/s/XXXXXXXX&direct=true"
```

**Pattern 3: Proxy Modes**
Direct access to the Cloudflare Worker proxy with multiple modes for different use cases.

**Mode: `resolve` (Recommended)**
Auto extract jsToken + fetch share API in one call.
```bash
curl "http://localhost:5000/api?mode=resolve&surl=abc123"
```

**Mode: `lookup` (🚀 Fastest)**
Query the D1 database cache directly with no upstream calls. Requires `surl` or `fid`.
```bash
curl "http://localhost:5000/api?mode=lookup&surl=abc123"
```

**Mode: `page`**
Proxy raw share HTML page for debugging.
```bash
curl "http://localhost:5000/api?mode=page&surl=abc123"
```

**Mode: `api`**
Manual share API proxy when jsToken is already known.
```bash
curl "http://localhost:5000/api?mode=api&jsToken=XYZ&shorturl=abc123"
```

**Mode: `stream`**
Fetch and rewrite M3U8 playlist for HLS streaming.
```bash
curl "http://localhost:5000/api?mode=stream&surl=abc123"
# Optional: specify quality
curl "http://localhost:5000/api?mode=stream&surl=abc123&type=M3U8_AUTO_720"
```

**Mode: `segment`**
Proxy media segments (.ts, .m4s) - used automatically by rewritten playlists.
```bash
curl "http://localhost:5000/api?mode=segment&url=ENCODED_URL"
```

**Mode: `health`**
Check the health status of the worker service.
```bash
curl "http://localhost:5000/api?mode=health"
```

**Notes**:
- Cookies are forwarded from client request if provided in `Cookie` header
- Use `mode=resolve` for most use cases
- `stream` and `segment` modes enable HLS video playback in browsers and players
- Legacy `/api?url=...` usage remains fully supported

#### `GET /admin/*` - Admin Endpoints
Path-based admin endpoints to inspect database records and analytics. All requests require authentication if configured in the worker. Pass the key using either `?key=YOUR_ADMIN_KEY` or `x-admin-key` header.
- `GET /admin/overview`: Summary metrics of shares and files
- `GET /admin/shares`: Search and list resolved shares
- `GET /admin/files`: Search and filter media files
- `GET /admin/kv/entry?surl=...`: Lookup raw cached D1 share record

---

## Supported TeraBox Domains

The API validates and supports the following TeraBox domains:
- `terabox.app`
- `teraboxshare.com`
- `terabox.com`
- `1024terabox.com`
- `teraboxlink.com`
- `terasharefile.com`
- `terafileshare.com`
- `terasharelink.com`

Both `http://` and `https://` protocols are supported.

---

## Integration Examples

You can easily query the gateway API using your preferred programming language. Here are examples of retrieving direct download links for a TeraBox share URL using `/api?direct=true`:

### 🐍 Python (using `requests`)

```python
import requests

def get_direct_links(gateway_url, share_url):
    response = requests.get(
        f"{gateway_url}/api",
        params={"url": share_url, "direct": "true"}
    )
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "success":
            for file in data.get("files", []):
                print(f"File: {file['filename']}")
                print(f"Size: {file['size']}")
                print(f"Direct Link: {file['download_link']}\n")
        else:
            print("Error:", data.get("message"))
    else:
        print("HTTP Error:", response.status_code)

# Example Usage:
# get_direct_links("http://localhost:5000", "https://teraboxshare.com/s/1LNr3tyl5pI5KUM8BecGtyQ")
```

### 🟨 JavaScript (Node.js / Browser)

```javascript
async function getDirectLinks(gatewayUrl, shareUrl) {
    try {
        const response = await fetch(`${gatewayUrl}/api?url=${encodeURIComponent(shareUrl)}&direct=true`);
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            data.files.forEach(file => {
                console.log(`File: ${file.filename}`);
                console.log(`Size: ${file.size}`);
                console.log(`Direct Link: ${file.download_link}\n`);
            });
        } else {
            console.error('Error:', data.message || 'Failed to resolve links');
        }
    } catch (error) {
        console.error('Fetch Error:', error);
    }
}

// Example Usage:
// getDirectLinks("http://localhost:5000", "https://teraboxshare.com/s/1LNr3tyl5pI5KUM8BecGtyQ");
```

### 🐹 Go

```go
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
)

type FileItem struct {
	Filename     string `json:"filename"`
	Size         string `json:"size"`
	DownloadLink string `json:"download_link"`
}

type APIResponse struct {
	Status string     `json:"status"`
	Files  []FileItem `json:"files"`
}

func getDirectLinks(gatewayURL, shareURL string) {
	resp, err := http.Get(fmt.Sprintf("%s/api?url=%s&direct=true", gatewayURL, url.QueryEscape(shareURL)))
	if err != nil {
		fmt.Println("Error:", err)
		return
	}
	defer resp.Body.Close()

	var result APIResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		fmt.Println("Decode Error:", err)
		return
	}

	if result.Status == "success" {
		for _, file := range result.Files {
			fmt.Printf("File: %s\nSize: %s\nDirect Link: %s\n\n", file.Filename, file.Size, file.DownloadLink)
		}
	} else {
		fmt.Println("API returned an error status")
	}
}

func main() {
	// getDirectLinks("http://localhost:5000", "https://teraboxshare.com/s/1LNr3tyl5pI5KUM8BecGtyQ")
}
```

---

## Environment Variables

You can configure the API using environment variables in your `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `COOKIE_JSON` | TeraBox cookies (simple string or JSON) | - |
| `TERABOX_COOKIES_JSON` | Alternative: JSON string of cookies | - |
| `TERABOX_COOKIES_FILE` | Alternative: Path to cookies JSON file | - |
| `HOST` | Server host address | `0.0.0.0` |
| `PORT` | Server port | `5000` |
| `FLASK_DEBUG` | Enable Flask debug mode (`1` or `0`) | `0` |
| `RATE_LIMIT` | Max requests per window per IP | `30` |
| `RATE_WINDOW` | Rate limit window size in seconds | `60` |
| `CACHE_TTL` | Cache entry time-to-live in seconds | `60` |
| `CACHE_MAX_SIZE` | Maximum number of cached entries | `500` |

**Cookie Priority**:
1. `COOKIE_JSON` (from `.env`)
2. `TERABOX_COOKIES_JSON`
3. `TERABOX_COOKIES_FILE`

---

## Technical Implementation

### Unified Proxy Architecture

The TeraBox Gateway uses a **unified Cloudflare Worker proxy** for all TeraBox API interactions. This architecture provides:

- **Reduced Network Overhead**: 33-50% fewer HTTP requests (1-2 instead of 2-3 per request)
- **Server-Side Token Handling**: Automatic jsToken extraction handled by the proxy
- **Mode-Based Operations**: Three distinct modes for different use cases

#### Proxy Modes

The unified proxy supports 5 distinct modes, all accessible via the `/proxy` endpoint:

**1. `mode=resolve` (Recommended)**
- Automatically fetches the share page, extracts jsToken, and returns file metadata
- **Single HTTP call** for most common use cases
- Returns JSON with file list and metadata
- Best for production use

**2. `mode=page`**
- Returns raw HTML of TeraBox share page
- Useful for debugging and manual token extraction
- Returns HTML content

**3. `mode=api`**
- Direct API access when jsToken is already known
- Used for directory listings and advanced scenarios
- Returns JSON from TeraBox API

**4. `mode=stream`**
- Fetches M3U8 playlist and rewrites segment URLs
- Requires `surl` parameter (short URL ID)
- Optional `type` parameter for quality selection (default: M3U8_AUTO_360)
- Enables HLS video streaming in browsers and players
- Returns modified M3U8 playlist

**5. `mode=segment`**
- Proxies individual video segments (.ts, .m4s files)
- Automatically used by rewritten playlists
- Returns binary media data

### Request Flow

```
Client Request → Flask API → Unified Proxy (mode=resolve) → TeraBox API → Response
               ↓
         (if directory)
               ↓
         Unified Proxy (mode=api) → Directory Contents → Response
```

**Key Benefits**:
- ✅ Simplified codebase with no manual token parsing
- ✅ Faster response times due to fewer roundtrips
- ✅ More reliable token extraction (handled server-side)
- ✅ Better error handling and reporting

For detailed proxy documentation, see [tboxproxy_usage.md](tboxproxy_usage.md).

---

## Deployment

### Deploy to Vercel

The easiest way to deploy your own instance of the TeraBox Gateway API is to use Vercel.

Click the button below to clone and deploy this repository with one click:

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fsaahiyo%2Fterabox-gateway&env=COOKIE_JSON)

Alternatively, deploy manually using the Vercel CLI:

1. Install Vercel CLI (optional):
   ```bash
   npm i -g vercel
   ```

2. Deploy:
   ```bash
   vercel
   ```

3. Set environment variables in Vercel dashboard:
   - Go to your project settings
   - Add `COOKIE_JSON` with your `ndus` token value

The `vercel.json` configuration is already set up for you.

---

## Troubleshooting

### Common Issues

**Error 400141 - Verification Required**
- The link is password-protected
- Solution: Add `&pwd=PASSWORD` parameter to your request

**HTTP 5xx Errors**
- Your cookies may have expired
- Solution: Update your `ndus` cookie following the steps above

**No Direct Link Returned**
- Cookies are invalid or expired
- The share link itself has expired
- Solution: Refresh cookies or verify the link is still active

**"Cookies not loaded" Warning**
- `.env` file is missing or `COOKIE_JSON` is not set
- Solution: Create `.env` file and add your `ndus` token

**Authentication Failures**
- The `ndus` token is invalid or malformed
- Solution: Copy the token again from your browser, ensuring no extra spaces

---

## Development

### Running in Debug Mode

Set `FLASK_DEBUG=1` in your `.env` file:

```env
FLASK_DEBUG=1
```

This enables:
- Auto-reload on code changes
- Detailed error pages
- Interactive debugger

### Logging

The API uses Python's `logging` module with INFO level by default. Logs include:
- Request URLs and parameters
- Cookie loading status (format detection)
- API responses and errors
- Share page tokens and authentication status

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## Contact

For questions or support, contact [@Saahiyo](https://github.com/Saahiyo)

---

## Acknowledgments

- Built with Flask 3.x (native async) and aiohttp for efficient async operations
- Unified Cloudflare Worker proxy for optimized API access
- Designed for seamless Vercel deployment
- Supports multiple TeraBox domains and share URL formats
