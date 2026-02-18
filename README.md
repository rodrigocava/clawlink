# ClawLink 🦞🔗

> Connect your phone's context to your OpenClaw AI agent — privately.

ClawLink is an **encrypted data relay** between the ClawLink mobile app (iOS & Android) and any OpenClaw instance. Your health, activity, and context data is encrypted before it ever leaves your device. The server stores only opaque blobs it cannot read.

---

## Quick start

```bash
git clone https://github.com/rodrigocava/clawlink.git
cd clawlink
make run
```

Server starts on **http://localhost:8000**  
API docs at **http://localhost:8000/docs**

> **AI agent?** Read [AGENTS.md](./AGENTS.md) for concise deploy + operate instructions.

---

## How it works

```
Mobile App  →  encrypt data locally  →  POST /sync  →  opaque blob stored on server
OpenClaw    →  GET /sync/{token}     →  decrypt locally  →  analyze + act
```

The server is **dumb by design** — it stores only encrypted blobs it cannot read.  
Even with full database access, no personal data is recoverable without your password.

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sync` | Upload encrypted payload |
| `GET` | `/sync/{token}` | Fetch latest payload |
| `DELETE` | `/sync/{token}` | Delete payload after processing |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive Swagger UI |
| `GET` | `/redoc` | ReDoc API reference |

---

## Configuration

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Port to expose |
| `DATA_TTL_HOURS` | `48` | Hours before payloads auto-expire |
| `MAX_PAYLOAD_BYTES` | `10485760` | Max upload size (10MB) |

---

## Make commands

```bash
make run      # Start (production, Docker)
make dev      # Start (local, auto-reload)
make stop     # Stop
make logs     # Tail logs
make test     # Health check
make update   # Pull latest + restart
```

---

## Deploy on a server

```bash
# 1. Clone
git clone https://github.com/rodrigocava/clawlink.git && cd clawlink

# 2. (Optional) configure
cp .env.example .env && nano .env

# 3. Run
make run

# 4. Verify
make test
```

Then point a reverse proxy or Cloudflare Tunnel at port 8000.

---

## Project components

| Component | Status | Description |
|-----------|--------|-------------|
| **ClawLink Server** | ✅ Ready | This repo — self-hostable relay |
| **ClawLink iOS** | 🔜 Soon | Swift/SwiftUI + HealthKit |
| **ClawLink Android** | 📅 Roadmap | — |
| **ClawLink Skill** | 🔜 Soon | OpenClaw integration |

---

## Data the app shares (V1)

- Sleep analysis (stages + duration)
- Heart Rate Variability (HRV)
- Resting heart rate
- Steps + active energy
- Activity type (walking, running, driving…)
- Focus mode + battery level

Schema is **versioned and evolvable** — new fields and modules are additive and backward compatible.

---

## Payload schema

```json
{
  "v": 1,
  "sent_at": "2026-02-18T10:00:00Z",
  "device": { "platform": "ios", "app_version": "1.0.0" },
  "modules": {
    "health": {
      "sleep": [{ "ts_start": "...", "ts_end": "...", "stage": "deep|rem|core|awake" }],
      "hrv": [{ "ts": "...", "value": 42, "unit": "ms" }],
      "heart_rate": [{ "ts": "...", "value": 68, "unit": "bpm" }],
      "steps": { "date": "2026-02-17", "count": 8432 },
      "active_energy": { "date": "2026-02-17", "value": 420, "unit": "kcal" }
    },
    "context": {
      "battery": 0.82,
      "focus_mode": "sleep",
      "activity_type": "stationary"
    }
  }
}
```

---

## Self-host vs hosted

| | Self-host | Hosted (cava.industries) |
|--|-----------|--------------------------|
| Cost | Free | ~$12-20/year |
| Setup | ~5 min with Docker | Zero config |
| Privacy | Your server, your rules | Encrypted blobs only — we can't read your data |
| Control | Full | Standard |

---

## License

MIT — fork it, self-host it, build on it.
