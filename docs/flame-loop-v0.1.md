# Flame Loop v0.1

## Commands
- `/mission <title> | <objective>`: create the next mission as active (only one active mission at a time). If no arguments, show the current mission. Use `/mission close FLAME-001` to close it.
- `/status`: show active mission state, blockers, proof count, and next move.
- `/outcome [mission_id]`: persist and display an outcome based on mission-linked proof records.
- `/nextmission [mission_id]`: persist a proposed follow-up mission. It is a proposal only; human approval is required before starting it.

## Evidence caveat
Proof hash submissions are recorded as **unverified**. This release does not query TON or verify transactions. Reports use aggregate counts and do not expose Telegram user IDs or submitted hashes.

## FLAME-001 execution
1. Deploy updated backend and ensure its SQLite database is writable/persistent.
2. In Telegram, send `/mission Flame Ignition | Launch the first Flame drop`.
3. Send `/status`; confirm FLAME-001 is active.
4. Manually produce and approve the content, then publish/dispatch through the existing approved channel.
5. Participants submit proof with existing `/proof <hash> [blessing]`. These records link to the active mission.
6. Send `/outcome FLAME-001`; review counts and limitations.
7. Send `/nextmission FLAME-001`; review the generated proposal.
8. If approved, close FLAME-001 with `/mission close FLAME-001`, then create FLAME-002 with `/mission <title> [objective]`.

## Operational requirements
- Back up the existing SQLite file before deploying.
- Preserve the Telegram webhook configuration and environment variables.
- No publication automation or on-chain verification is added.
