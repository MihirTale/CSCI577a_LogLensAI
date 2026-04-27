# Target Service

A small companion service used to **genuinely** trigger application errors that the LogLens dashboard then observes. Backend on **:8002**, frontend on **:5174**.

Errors are written to the same log file that LogLens already tails (`backend/logs/app.log`), so any trigger you fire here shows up in LogLens within a few seconds.

## Run

### Backend

```bash
cd target_service/backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
python main.py
```

API: <http://localhost:8002> (`/scenarios`, `POST /trigger/{id}`, `/recent`, `/health`).

### Frontend

```bash
cd target_service/frontend
npm install
npm run dev
```

Open <http://localhost:5174>. Click any scenario card to fire it; the backend will perform the failing operation and write structured `ERROR` / `WARN` lines into `backend/logs/app.log`.

## Available scenarios

| ID | Description |
|----|-------------|
| `db_timeout` | Order service times out hitting the DB connection pool |
| `null_pointer` | AttributeError when `session` is `None` in checkout |
| `oom` | Worker OOMs and is terminated |
| `auth_failure` | Repeated invalid-token attempts from a single IP |
| `api_failure` | Stripe returns 503 with revenue impact |
| `race_condition` | Inventory writes deadlock and a transaction rolls back |

## Configuration

| Var | Default | Purpose |
|-----|---------|---------|
| `TARGET_LOG_FILE` | `<repo>/backend/logs/app.log` | Log file path the service writes to. Override only if your LogLens backend uses a non-default location. |
