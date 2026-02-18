# ClawLink 🦞🔗

> Connect your phone's context to your OpenClaw AI agent — privately.

ClawLink is an encrypted data relay between the **ClawLink mobile app** (iOS & Android) and any **OpenClaw** instance. Your phone's health, activity, and context data is encrypted before it ever leaves your device.

## Privacy model

```
Mobile App  →  encrypts data client-side  →  POST /sync  →  opaque blob stored
OpenClaw    →  GET /sync/{token}  →  decrypt locally  →  analyze + act
```

The server is **dumb by design** — it stores only encrypted blobs it cannot read.  
Even with full database access, no personal data is recoverable without your password.

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sync` | Upload encrypted payload |
| `GET` | `/sync/{token}` | Fetch latest payload |
| `DELETE` | `/sync/{token}` | Delete payload |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive API docs (Swagger UI) |
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

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_PATH` | `sync.db` | Path to SQLite database |
| `DATA_TTL_HOURS` | `48` | Hours before payloads auto-expire |
| `MAX_PAYLOAD_BYTES` | `10485760` | Max upload size (10MB) |

## Project structure

```
ClawLink Server  (this repo)   — self-hostable relay, open source (MIT)
ClawLink iOS     (coming soon) — iPhone app, HealthKit + encryption
ClawLink Android (roadmap)     — Android app
ClawLink Skill   (coming soon) — OpenClaw integration (fetch + decrypt + analyze)
```

## License

MIT — fork it, self-host it, build on it.
