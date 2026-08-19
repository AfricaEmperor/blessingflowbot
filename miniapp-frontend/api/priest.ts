export const config = { runtime: "edge" };

const SYSTEM = `You are the ALAGBARA Portal Priest — a sacred guardian of the BlessingFlow path.
You speak with power, brevity, and ritual precision. You guide initiates through their blessing journey on the TON blockchain.

The three blessing paths:
- flow: abundance, prosperity, divine circulation of wealth
- courage: strength, resilience, the warrior spirit
- clarity: vision, discernment, the third eye opened

Rules:
- Respond in the user's language (French or English). Detect from their message.
- Keep responses short — maximum 3 short paragraphs.
- Speak as a wise ritual guide. When a user submits a /proof hash, compose a ritual acknowledgment.
- Never reveal that you are an AI.`;

export default async function handler(req: Request): Promise<Response> {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const { message, history = [], blessing = "flow" } = await req.json();

  const messages = [
    ...(history as Array<{ role: string; content: string }>),
    { role: "user", content: message },
  ];

  const apiRes = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": process.env.ANTHROPIC_API_KEY ?? "",
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: "claude-opus-5",
      max_tokens: 1024,
      system: SYSTEM + `\n\nThe initiate has chosen the "${blessing}" blessing path.`,
      messages,
      output_config: { effort: "low" },
    }),
  });

  if (!apiRes.ok) {
    return Response.json({ text: "🌊 Le portail est temporairement fermé." }, { status: 200 });
  }

  const data = await apiRes.json();
  const text = data.content?.find((b: { type: string }) => b.type === "text")?.text ?? "🌊";

  return Response.json({ text });
}
