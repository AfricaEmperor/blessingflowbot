# Flame Loop v0.1

```
MISSION -> EXECUTION -> EVIDENCE -> OUTCOME -> LEARNING -> NEXT MISSION
```

BlessingFlowBot now keeps the state of a mission, links every `/proof` to it, and
turns a closed mission into an outcome record plus a draft next mission.

Not in v0.1 (on purpose): a Command Room UI, a scheduler, a media engine, an
intelligence platform, automated publishing, on-chain proof verification.

## What was added

| Piece | Where |
|---|---|
| Mission state, proof records, outcome and next-mission generation | `backend/flame/` (standard library only) |
| Schema migration `001 flame_loop_v0_1` | `backend/flame/migrations.py` |
| Operator CLI | `python -m flame.cli` (run from `backend/`) |
| Telegram `/status` (everyone) and `/outcome` (admins) | `backend/main.py` |
| `/proof` links the proof to the active mission and records delivery | `backend/main.py` |

Tables added to the existing SQLite file: `missions`, `mission_proofs`,
`mission_events`, `mission_outcomes`, `flame_meta`, `schema_migrations`.
The existing `conversations` and `user_prefs` tables are not changed.

## How the loop works

1. **Mission.** A draft is created, a human activates it. Only one mission can be
   active at a time (enforced by the database).
2. **Execution.** You publish the drop yourself. People reach the bot and send
   `/proof <hash> [blessing]`.
3. **Evidence.** Each proof is stored against the active mission with its
   blessing, delivery status (`pending`, `delivered`, `failed`) and verification
   status. A repeated hash counts once. The Telegram user id is never stored in the
   new tables, only a salted hash used to count distinct participants.
4. **Outcome.** A human closes the mission. `outcome` writes evidence, result,
   decision and learning using fixed rules (no AI call), so it cannot invent evidence.
5. **Next mission.** A **draft** is created with the next id, linked to its parent.
   A human reviews it and activates it. Nothing starts by itself.

Result rules: `met` when proofs reach `target_proofs`, `partially met` at half or
more, `not met` below that, `inconclusive` when no target was set. Rejected proofs
do not count. Proofs stay `unverified` until a human marks them with `verify`, and
the decision text says so.

## Telegram

| Command | Who | What it does |
|---|---|---|
| `/status` | everyone | Active mission, its status, and the user's own proof count. English or French. |
| `/status` | admins (`FLAME_ADMIN_IDS`) | Adds goal, proofs vs target, participants, blessings, verification, deliveries, blockers, next move, drafts. |
| `/outcome [FLAME-nnn]` | admins | Generates (or shows) the outcome of a closed mission. Defaults to the latest closed one. |

Everyone else gets the normal "Unknown command" reply to `/outcome`.

## CLI (run from `backend/`)

```
python -m flame.cli init
python -m flame.cli create FLAME-001 --title "..." --goal "..." [--success "..."] [--target-proofs N] [--owner "..."] [--next-move "..."]
python -m flame.cli set FLAME-001 [--title ..] [--goal ..] [--target-proofs N] [--next-move ..] [--blocker "..."] [--clear-blockers]
python -m flame.cli activate FLAME-001
python -m flame.cli status [FLAME-001] [--json]
python -m flame.cli proofs [FLAME-001|none]
python -m flame.cli verify <proof_id> verified|rejected|unverified
python -m flame.cli close FLAME-001
python -m flame.cli outcome FLAME-001 [--json]
python -m flame.cli missions
```

Errors exit with code 2 and a plain message.

## Configuration

| Variable | Meaning |
|---|---|
| `FLAME_ADMIN_IDS` | Comma separated numeric Telegram user ids. Empty means no admins. |
| `FLAME_DB_PATH` | Optional. Defaults to `backend/db/blessing_memory.db`. |

## Executing FLAME-001

Do these in order. Anything in angle brackets is your decision.

1. **Python.** Use Python 3.11. `python-telegram-bot==13.15` does not import on
   Python 3.13 (`imghdr` was removed). 3.12 is untested.
   ```bash
   cd backend
   python3.11 -m venv .venv && . .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
2. **Tests.** Expect every test to pass before you go on.
   ```bash
   python -m pytest -q
   ```
3. **Blessing assets.** `dispatcher.py` reads `backend/assets/`, which is not in the
   repository. Add the files named in `blessings/blessing_assets.json`
   (for example `assets/flow/flow_qr.png`, `flow_whisper.mp3`, `flow_scroll.pdf`, and the
   same for `courage` and `clarity`). Without them the ritual reply still goes out, but
   the blessing delivery fails and the proof is marked `failed`.
4. **Environment.** Copy `.env.example` to `.env` and fill `BOT_TOKEN`, `WEBHOOK_URL`,
   `ANTHROPIC_API_KEY`, and `FLAME_ADMIN_IDS=<your numeric Telegram user id>`.
5. **Back up.** If `db/blessing_memory.db` exists:
   ```bash
   cp db/blessing_memory.db db/blessing_memory.db.bak-$(date +%F)
   ```
6. **Migrate.**
   ```bash
   python -m flame.cli init
   ```
   Expect `schema version 1 at .../backend/db/blessing_memory.db`.
7. **Define the mission as a draft.** Choose the wording and the target yourself.
   ```bash
   python -m flame.cli create FLAME-001 \
     --title "<mission title>" \
     --goal "<what this drop is meant to achieve>" \
     --success "<how you will judge it, in words>" \
     --target-proofs <number of proofs that counts as success> \
     --owner "<name>" \
     --next-move "Publish the drop"
   ```
8. **Start the bot and set the webhook** (existing steps).
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   python setup_webhook.py          # in a second terminal, with the same env
   ```
9. **Smoke test before activating.** From your admin account send `/status`
   (expect `No active mission.`) and `/proof SMOKETEST1 flow` (expect the ritual
   reply and the blessing assets). Then:
   ```bash
   python -m flame.cli proofs none
   ```
   You should see one proof with `delivered`. It is recorded outside any mission, so it
   does not count toward FLAME-001. If it says `failed`, fix the assets (step 3) first.
10. **Approve and activate.** Read the draft, then activate it.
    ```bash
    python -m flame.cli status FLAME-001
    python -m flame.cli activate FLAME-001
    ```
11. **Run the drop yourself.** Post to your channels by hand and point people to the
    bot. Publishing stays a human action.
12. **Watch it.** `/status` as admin in Telegram, or `python -m flame.cli status` and
    `python -m flame.cli proofs`.
13. **Verify proofs.** Check each transaction hash in a TON explorer, then mark it.
    ```bash
    python -m flame.cli verify <proof_id> verified      # or: rejected
    ```
14. **Close at the time you chose.**
    ```bash
    python -m flame.cli close FLAME-001
    ```
15. **Generate the outcome and the draft next mission.**
    ```bash
    python -m flame.cli outcome FLAME-001
    ```
    (Admins can send `/outcome` in Telegram instead.)
16. **Review FLAME-002.** It is only a draft. Edit it, then activate it when ready.
    ```bash
    python -m flame.cli set FLAME-002 --goal "<your wording>" --target-proofs <N>
    python -m flame.cli activate FLAME-002
    ```

**Complete** when FLAME-001 has an outcome record and a reviewed FLAME-002 came from it.
**Repeatable** when FLAME-002 runs through steps 10 to 15 with no code change.

## Roll back

The migration only adds tables. To switch the loop off, stop the bot and restore the
backup from step 5 (or delete the new tables). `/proof` keeps working without the
loop: if the mission store fails, the ritual still runs and the error is logged.

## Known limits

- Proofs are **not verified on-chain** by the bot. `/proof` still replies "verified"
  in its fallback text; the stored status stays `unverified` until you mark it.
- `backend/logs/proofs.json` (legacy, tracked in git) still records raw Telegram user
  ids. Do not commit runtime copies of it.
- Outcome and learning text is rules-based and short by design.
- No scheduler, Command Room or automated distribution.
