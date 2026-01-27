# TeraBox Gateway API

A lightweight Flask-based API for extracting file information and direct download links from TeraBox share URLs.

This project provides:
- **Web API** with endpoints for listing files and retrieving direct links
- **Unified Cloudflare Worker Proxy** for optimized TeraBox API access
- **Vercel-ready deployment** configuration
- **Flexible cookie authentication** with support for simple string or JSON formats

The API uses `aiohttp` for asynchronous requests and leverages a unified Cloudflare Worker proxy with mode-based operations for efficient TeraBox API interaction.

---

## Features

- **Web API Endpoints**:
  - `GET /api`: Lists files with metadata, including file size, thumbnails, and paths
  - `GET /api2`: Retrieves file metadata and resolves direct download links
  - `GET /help`: Provides inline documentation for the API
  - `GET /health`: Simple health check endpoint
  - `GET /`: API information and status

- **Flexible Cookie Configuration**:
  - Simple string format: Just paste your `ndus` token
  - Full JSON format: Supports multiple cookie fields
  - Environment variable or file-based configuration

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
├── main.py               # Entry point for running Flask locally
├── .env                  # Environment variables (not tracked in git)
├── .env.example          # Example environment configuration
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project metadata
├── vercel.json           # Vercel deployment configuration
├── tboxproxy_usage.md    # Unified proxy API documentation
├── .gitignore            # Git ignore file
├── LICENSE               # MIT License
├── README.md             # This file
└── endpoints/            # Reserved for future route modularization
```

---

## Requirements

- **Python 3.9+**
- **Dependencies**:
  - `Flask==2.2.5`
  - `Werkzeug==2.2.3`
  - `aiohttp>=3.8,<4`
  - `requests>=2.31,<3`

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

#### `GET /help` - API Documentation
Provides detailed inline documentation and usage examples.

```bash
curl http://localhost:5000/help
```

#### `GET /api` - Get File Information
Retrieves file metadata for a TeraBox share link.

**Parameters**:
- `url` (required): TeraBox share URL
- `pwd` (optional): Password for protected links

**Example**:
```bash
curl "http://localhost:5000/api?url=https://1024terabox.com/s/1LNr3tyl5pI5KUM8BecGtyQ"
```

**Response** (success):
```json
{
  "files": [
    {
      "download_link": "https://d.terabox.app/file/...?fid=xxx&dstime=xxx&sign=xxx...",
      "filename": "VID_202.ts",
      "fs_id": "305771137601214",
      "is_directory": false,
      "path": "/2025-10-06 01-28/VID_202.ts",
      "size": "6.57 MB",
      "size_bytes": 6891328,
      "thumbnails": {
        "60x60": "https://data.terabox.app/thumbnail/...?size=c60_u60&quality=100...",
        "140x90": "https://data.terabox.app/thumbnail/...?size=c140_u90&quality=100...",
        "360x270": "https://data.terabox.app/thumbnail/...?size=c360_u270&quality=100...",
        "850x580": "https://data.terabox.app/thumbnail/...?size=c850_u580&quality=100..."
      }
    }
  ],
  "status": "success",
  "timestamp": "2026-01-17T11:30:32.672789",
  "total_files": 1,
  "url": "https://1024terabox.com/s/1LNr3tyl5pI5KUM8BecGtyQ"
}
```

#### `GET /api2` - Get Direct Download Links
Retrieves file metadata and resolves direct download links by following redirects.

**Parameters**:
- `url` (required): TeraBox share URL
- `pwd` (optional): Password for protected links

**Example**:
```bash
curl "http://localhost:5000/api2?url=https://teraboxshare.com/s/XXXXXXXX"
```

**Response**: Similar to `/api` but includes `direct_link` field for each file.

---

## Supported TeraBox Domains

The API validates and supports the following TeraBox domains:
- `terabox.app`
- `teraboxshare.com`
- `terabox.com`
- `1024terabox.com`

Both `http://` and `https://` protocols are supported.

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

**1. `mode=resolve` (Default)**
- Automatically fetches the share page, extracts jsToken, and returns file metadata
- **Single HTTP call** for most common use cases
- Recommended for production use

**2. `mode=page`**
- Returns raw HTML of TeraBox share page
- Useful for debugging and manual token extraction

**3. `mode=api`**
- Direct API access when jsToken is already known
- Used for directory listings and advanced scenarios

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

This project is configured for easy deployment to Vercel:

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

- Built with Flask and aiohttp for efficient async operations
- Unified Cloudflare Worker proxy for optimized API access
- Designed for seamless Vercel deployment
- Supports multiple TeraBox domains and share URL formats