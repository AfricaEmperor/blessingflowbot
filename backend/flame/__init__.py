"""Flame Loop v0.1: persistent mission state for BlessingFlowBot.

MISSION -> EXECUTION -> EVIDENCE -> OUTCOME -> LEARNING -> NEXT MISSION

Standard library only. Persistence is the same SQLite file the bot already
uses (override with FLAME_DB_PATH). Nothing in here imports Telegram.
"""
