"""Deterministic outcome rules. Pure functions: no database, no network, no LLM.

The outcome only states what the recorded evidence supports. It never claims
a proof is verified unless a human marked it so.
"""
import math

def _n(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


MET = "met"
PARTIAL = "partially met"
NOT_MET = "not met"
INCONCLUSIVE = "inconclusive"


def judge(target, counted: int) -> str:
    if not target:
        return INCONCLUSIVE
    if counted >= target:
        return MET
    if counted * 2 >= target:
        return PARTIAL
    return NOT_MET


def _top_blessing(by_blessing: dict):
    if not by_blessing:
        return None
    best = max(by_blessing.values())
    leaders = sorted(k for k, v in by_blessing.items() if v == best)
    return leaders, best


def decide(result: str, counted: int, unverified: int) -> str:
    if counted == 0:
        decision = (
            "Hold. No proofs were recorded. Check that the drop and the entry link "
            "reached people before repeating."
        )
    elif result == MET:
        decision = "Repeat. The target was reached. Raise it for the next mission."
    elif result == INCONCLUSIVE:
        decision = (
            "Adjust. No target was set, so the result cannot be judged. "
            "Set target_proofs on the next mission."
        )
    else:
        decision = (
            "Adjust. The target was not reached. Change the drop or the entry "
            "before repeating."
        )
    if counted and unverified:
        decision += f" Evidence is self-reported: {unverified} of {counted} proofs are unverified."
    return decision


def learn(stats: dict, conversations, duplicates: int) -> list:
    counted = stats["counted"]
    lines = []
    top = _top_blessing(stats["by_blessing"])
    if counted and top:
        leaders, n = top
        if len(leaders) == 1:
            lines.append(f"Most proofs chose '{leaders[0]}' ({n} of {counted}).")
        else:
            lines.append(f"Blessings tied for most proofs: {', '.join(leaders)} ({n} each).")
    if stats["failed"]:
        n = stats["failed"]
        lines.append(
            f"{_n(n, 'blessing delivery', 'blessing deliveries')} failed. Check the asset files "
            "and the logs before the next drop."
        )
    if stats["pending"] and counted:
        lines.append(f"{_n(stats['pending'], 'delivery', 'deliveries')} never completed.")
    if counted:
        if stats["verified"] == 0:
            lines.append(
                f"None of the {counted} proofs were verified. Verify them against the "
                "chain or treat the result as self-reported."
            )
        elif stats["unverified"]:
            lines.append(f"{stats['verified']} of {counted} proofs were verified.")
        else:
            lines.append(f"All {counted} proofs were verified.")
    if stats["participants"] and counted > stats["participants"]:
        lines.append(
            f"Some people sent several proofs ({_n(stats['participants'], 'participant', 'participants')}, "
            f"{counted} proofs)."
        )
    if duplicates:
        was = "was" if duplicates == 1 else "were"
        lines.append(f"{_n(duplicates, 'duplicate submission', 'duplicate submissions')} {was} ignored.")
    if conversations:
        was = "was" if conversations == 1 else "were"
        lines.append(f"{_n(conversations, 'message', 'messages')} {was} exchanged with the portal priest during the mission.")
    if not lines:
        lines.append("Nothing to learn yet: no proofs and no conversation were recorded.")
    return lines


def next_target(result: str, target, counted: int):
    if result == MET and target:
        return math.ceil(target * 1.25)
    if result == INCONCLUSIVE:
        return counted if counted > 0 else None
    return target


def evaluate(mission: dict, stats: dict, conversations=None, duplicates: int = 0) -> dict:
    counted = stats["counted"]
    result = judge(mission.get("target_proofs"), counted)
    decision = decide(result, counted, stats["unverified"])
    learning = learn(stats, conversations, duplicates)
    target = next_target(result, mission.get("target_proofs"), counted)
    sentence = decision.split(". ", 1)
    goal = f"Continue from {mission['id']} ({mission['title']}). {sentence[0]}."
    evidence = {
        "proofs_counted": counted,
        "participants": stats["participants"],
        "by_blessing": stats["by_blessing"],
        "verified": stats["verified"],
        "unverified": stats["unverified"],
        "rejected": stats["rejected"],
        "deliveries": {
            "delivered": stats["delivered"],
            "failed": stats["failed"],
            "pending": stats["pending"],
        },
        "duplicate_submissions_ignored": duplicates,
        "first_proof_at": stats["first_at"],
        "last_proof_at": stats["last_at"],
        "target_proofs": mission.get("target_proofs"),
        "conversation_messages": conversations,
    }
    return {
        "evidence": evidence,
        "result": result,
        "decision": decision,
        "learning": learning,
        "next": {
            "title": f"Next cycle after {mission['id']}",
            "goal": goal,
            "success_measure": mission.get("success_measure", ""),
            "target_proofs": target,
            "owner": mission.get("owner", ""),
            "next_move": "Review this draft, adjust it, then activate it.",
        },
    }
