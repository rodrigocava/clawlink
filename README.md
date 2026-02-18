# OpenClaw Sync

Encrypted data relay between the **OpenClaw Companion** iOS app and any OpenClaw instance.

> **Privacy first:** The server stores only encrypted blobs. Plaintext health data never leaves your device.

## How it works

```
iPhone App  →  encrypts data  →  POST /sync  →  stored as opaque blob
OpenClaw    →  GET /sync/{token}  →  decrypt locally  →  analyze + act
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sync` | Upload encrypted payload |
| `GET` | `/sync/{token}` | Fetch latest payload |
| `DELETE` | `/sync/{token}` | Delete payload |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive API docs (Swagger) |
| `GET` | `/redoc` | API docs (ReDoc) |

## Running locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000/docs

## Running with Docker

```bash
docker compose up -d
```

## Self-hosting

Point your own domain at port 8000 via your reverse proxy of choice (Nginx, Caddy, Cloudflare Tunnel, etc.).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `sync.db` | Path to SQLite database |
| `DATA_TTL_HOURS` | `48` | Hours before payloads auto-expire |
| `MAX_PAYLOAD_BYTES` | `10485760` | Max upload size (10MB) |

## License

MIT — fork it, self-host it, build on it.
