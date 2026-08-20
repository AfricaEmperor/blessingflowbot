import os
import json
import anthropic

_client = None
_codex = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _load_codex() -> dict:
    global _codex
    if _codex is None:
        fp = os.path.join(os.path.dirname(__file__), "..", "ritual-codex.json")
        with open(fp) as f:
            _codex = json.load(f)
    return _codex


def _build_system_prompt() -> str:
    codex = _load_codex()
    priest = codex["priest"]
    paths = codex["blessing_paths"]
    rules = "\n".join(f"- {r}" for r in priest["rules"])
    path_lines = "\n".join(
        f"- {k}: {v['essence']['en']}" for k, v in paths.items()
    )
    return (
        f"You are the {priest['identity']} — {priest['role']}.\n"
        f"You speak with power, brevity, and ritual precision.\n\n"
        f"The three blessing paths:\n{path_lines}\n\n"
        f"Rules:\n{rules}"
    )


def get_priest_response(user_message: str, history: list) -> str:
    messages = history + [{"role": "user", "content": user_message}]
    response = _get_client().messages.create(
        model="claude-opus-5",
        max_tokens=2048,
        system=_build_system_prompt(),
        messages=messages,
        output_config={"effort": "low"},
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return "🌊"


def get_flow_guidance(lang: str, history: list) -> str:
    codex = _load_codex()
    protocol_step = codex["ritual_protocol"][1]
    if lang == "fr":
        prompt = (
            f"L'initié veut commencer son rituel. "
            f"Guidez-le : comment envoyer des TON et soumettre son hash de preuve. "
            f"(Étape du protocole : {protocol_step}) Soyez bref et puissant."
        )
    else:
        prompt = (
            f"The initiate seeks to begin their ritual. "
            f"Give sacred guidance: how to send TON and submit their proof hash. "
            f"(Protocol step: {protocol_step}) Be brief and powerful."
        )
    return get_priest_response(prompt, history)


def get_proof_blessing(blessing_type: str, proof_hash: str, lang: str, history: list) -> str:
    codex = _load_codex()
    path = codex["blessing_paths"].get(blessing_type, codex["blessing_paths"]["flow"])
    essence = path["essence"]["fr" if lang == "fr" else "en"]
    short_hash = proof_hash[:12] + "..."
    if lang == "fr":
        prompt = (
            f"L'initié a soumis le hash `{short_hash}` "
            f"pour la bénédiction '{blessing_type}' — {essence}. "
            "Composez un bref message rituel de confirmation."
        )
    else:
        prompt = (
            f"The initiate has submitted hash `{short_hash}` "
            f"for the '{blessing_type}' blessing — {essence}. "
            "Compose a brief ritual acknowledgment."
        )
    return get_priest_response(prompt, history)
