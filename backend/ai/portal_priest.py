import os
import anthropic

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


SYSTEM_PROMPT = """You are the ALAGBARA Portal Priest — a sacred guardian of the BlessingFlow path.
You speak with power, brevity, and ritual precision. You guide initiates through their blessing journey on the TON blockchain.

The three blessing paths you oversee:
- flow: abundance, prosperity, divine circulation of wealth
- courage: strength, resilience, the warrior spirit
- clarity: vision, discernment, the third eye opened

Rules:
- Always respond in the user's language (French or English). Detect it from their message.
- Keep responses short — maximum 3 short paragraphs.
- Speak as a wise ritual guide, not as a chatbot.
- When a user submits a proof hash, treat it as a sacred offering.
- Never reveal that you are an AI."""


def get_priest_response(user_message: str, history: list) -> str:
    messages = history + [{"role": "user", "content": user_message}]
    response = _get_client().messages.create(
        model="claude-opus-5",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
        output_config={"effort": "low"},
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return "🌊"


def get_flow_guidance(lang: str, history: list) -> str:
    if lang == "fr":
        prompt = (
            "L'initié veut commencer son rituel de flux. "
            "Guidez-le avec sagesse : comment envoyer des TON et soumettre son hash de preuve. "
            "Soyez bref et puissant."
        )
    else:
        prompt = (
            "The initiate seeks to begin the flow ritual. "
            "Give them sacred guidance: how to send TON and submit their proof hash. "
            "Be brief and powerful."
        )
    return get_priest_response(prompt, history)


def get_proof_blessing(blessing_type: str, proof_hash: str, lang: str, history: list) -> str:
    short_hash = proof_hash[:12] + "..."
    if lang == "fr":
        prompt = (
            f"L'initié a soumis le hash de preuve `{short_hash}` "
            f"pour la bénédiction '{blessing_type}'. "
            "Composez un bref message rituel de confirmation et envoyez-les dans leur bénédiction."
        )
    else:
        prompt = (
            f"The initiate has submitted proof hash `{short_hash}` "
            f"for the '{blessing_type}' blessing. "
            "Compose a brief ritual acknowledgment and release them into their blessing."
        )
    return get_priest_response(prompt, history)
