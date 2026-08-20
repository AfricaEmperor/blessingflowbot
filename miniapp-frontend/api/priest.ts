import codex from "../ritual-codex.json";

export const config = { runtime: "edge" };

type BlessingKey = keyof typeof codex.blessing_paths;

function buildSystemPrompt(blessing: string): string {
  const { priest, blessing_paths } = codex;
  const path = blessing_paths[(blessing as BlessingKey)] ?? blessing_paths.flow;
  const rules = priest.rules.map((r) => `- ${r}`).join("\n");
  const paths = (Object.entries(blessing_paths) as [string, { essence: { en: string } }][])
    .map(([k, v]) => `- ${k}: ${v.essence.en}`)
    .join("\n");

  return (
    `You are the ${priest.identity} — ${priest.role}.\n` +
    `You speak with power, brevity, and ritual precision.\n\n` +
    `The three blessing paths:\n${paths}\n\n` +
    `Active path for this initiate: ${path.essence.en}\n\n` +
    `Rules:\n${rules}`
  );
}

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
      system: buildSystemPrompt(blessing),
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
