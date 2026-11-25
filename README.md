# BlessingFlowBot

## Setup (Backend)
1. Copy `.env.example` to `.env` and fill values.
2. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. Expose via HTTPS and run:
   ```bash
   python setup_webhook.py
   ```

## Mini-App (Frontend)
1. `cd miniapp-frontend`
2. `npm install`
3. `npm run dev`

## Testing
- Use ngrok or Caddy for HTTPS local dev.
- In Telegram, interact with `@YourBot`: `/start`, `/flow`, `/proof ABC123`.
- Inspect `backend/logs/proofs.json` and `console/console_notebook.md`.

## Flame Loop v0.1 (missions, evidence, outcomes)
See `docs/flame-loop.md`. Quick checks:
```bash
cd backend
pip install -r requirements-dev.txt   # Python 3.11
python -m pytest -q
python -m flame.cli --help
```
