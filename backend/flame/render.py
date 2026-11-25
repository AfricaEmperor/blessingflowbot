"""Text for /status and the outcome report. Plain text only (no Markdown parse risk)."""

_L = {
    "en": {
        "none": "No active mission.",
        "mission": "Mission",
        "status": "Status",
        "yours": "Your proofs",
        "goal": "Goal",
        "proofs": "Proofs",
        "of_target": "of {t} target ({p}%)",
        "no_target": "(no target set)",
        "participant": "participant",
        "participants": "participants",
        "blessings": "Blessings",
        "verification": "Verification",
        "deliveries": "Deliveries",
        "blockers": "Blockers",
        "none_word": "none",
        "next": "Next move",
        "drafts": "Drafts waiting",
        "pending_outcome": "Closed, outcome not generated",
        "unlinked": "Proofs outside any mission",
        "verified": "verified",
        "unverified": "unverified",
        "rejected": "rejected",
        "delivered": "delivered",
        "failed": "failed",
        "pending": "pending",
    },
    "fr": {
        "none": "Aucune mission active.",
        "mission": "Mission",
        "status": "Statut",
        "yours": "Vos preuves",
        "goal": "Objectif",
        "proofs": "Preuves",
        "of_target": "sur {t} visées ({p}%)",
        "no_target": "(aucun objectif chiffré)",
        "participant": "participant",
        "participants": "participants",
        "blessings": "Bénédictions",
        "verification": "Vérification",
        "deliveries": "Livraisons",
        "blockers": "Blocages",
        "none_word": "aucun",
        "next": "Prochaine étape",
        "drafts": "Brouillons en attente",
        "pending_outcome": "Clôturée, bilan non généré",
        "unlinked": "Preuves hors mission",
        "verified": "vérifiées",
        "unverified": "non vérifiées",
        "rejected": "rejetées",
        "delivered": "livrées",
        "failed": "échouées",
        "pending": "en attente",
    },
}


def _t(lang):
    return _L.get(lang, _L["en"])


def render_status(snap: dict, lang: str = "en", admin: bool = False, user_proofs=None) -> str:
    t = _t(lang)
    mission = snap["mission"]
    lines = []
    if not mission:
        lines.append(t["none"])
    elif not admin:
        lines.append(f"🔥 {t['mission']} {mission['id']} · {mission['title']}")
        lines.append(f"{t['status']}: {mission['status']}")
        if user_proofs is not None:
            lines.append(f"{t['yours']}: {user_proofs}")
    else:
        p = snap["proofs"]
        pr = snap["progress"]
        lines.append(f"🔥 {t['mission']} {mission['id']} · {mission['title']} ({mission['status']})")
        lines.append(f"{t['goal']}: {mission['goal']}")
        target = t["of_target"].format(t=pr["target"], p=pr["pct"]) if pr["target"] else t["no_target"]
        who = t["participant"] if p["participants"] == 1 else t["participants"]
        lines.append(f"{t['proofs']}: {p['counted']} {target} · {p['participants']} {who}")
        if p["by_blessing"]:
            lines.append(f"{t['blessings']}: " + ", ".join(f"{k} {v}" for k, v in p["by_blessing"].items()))
        lines.append(f"{t['verification']}: {p['verified']} {t['verified']}, {p['unverified']} {t['unverified']}"
                     + (f", {p['rejected']} {t['rejected']}" if p["rejected"] else ""))
        lines.append(f"{t['deliveries']}: {p['delivered']} {t['delivered']}, {p['failed']} {t['failed']}, "
                     f"{p['pending']} {t['pending']}")
        blockers = "; ".join(mission["blockers"]) if mission["blockers"] else t["none_word"]
        lines.append(f"{t['blockers']}: {blockers}")
        if mission["next_move"]:
            lines.append(f"{t['next']}: {mission['next_move']}")
    if admin:
        if snap["drafts"]:
            lines.append(f"{t['drafts']}: {', '.join(snap['drafts'])}")
        if snap["closed_without_outcome"]:
            lines.append(f"{t['pending_outcome']}: {', '.join(snap['closed_without_outcome'])}")
        if snap["unlinked_proofs"]:
            lines.append(f"{t['unlinked']}: {snap['unlinked_proofs']}")
    return "\n".join(lines)


def render_outcome(outcome: dict, mission: dict, next_mission=None) -> str:
    """Operator report. English only."""
    ev = outcome["evidence"]
    lines = [f"Outcome · {mission['id']} · {mission['title']}", ""]
    blessings = ", ".join(f"{k} {v}" for k, v in ev["by_blessing"].items()) or "none"
    d = ev["deliveries"]
    lines += [
        "EVIDENCE",
        f"- {ev['proofs_counted']} {'proof' if ev['proofs_counted'] == 1 else 'proofs'} from "
        f"{ev['participants']} {'participant' if ev['participants'] == 1 else 'participants'} ({blessings})",
        f"- Verification: {ev['verified']} verified, {ev['unverified']} unverified, {ev['rejected']} rejected",
        f"- Deliveries: {d['delivered']} delivered, {d['failed']} failed, {d['pending']} pending",
    ]
    if ev["conversation_messages"] is not None:
        lines.append(f"- Conversation messages during the mission: {ev['conversation_messages']}")
    target = ev["target_proofs"]
    lines += ["", "RESULT", f"- {outcome['result']}" + (f" ({ev['proofs_counted']} of {target})" if target else ""),
              "", "DECISION", f"- {outcome['decision']}", "", "LEARNING"]
    lines += [f"- {item}" for item in outcome["learning"]]
    if next_mission:
        tgt = next_mission["target_proofs"] or "not set"
        lines += ["", f"NEXT MISSION (draft, needs your review): {next_mission['id']}",
                  f"- Goal: {next_mission['goal']}", f"- Target proofs: {tgt}"]
    return "\n".join(lines)
