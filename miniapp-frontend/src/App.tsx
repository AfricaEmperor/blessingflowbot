import React, { useState, useRef, useEffect } from "react";

type BlessingType = "flow" | "courage" | "clarity";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const BLESSINGS: Record<BlessingType, { emoji: string; label: string; desc: string }> = {
  flow:    { emoji: "🌊", label: "Flow",    desc: "Abondance · Prospérité · Circulation Divine" },
  courage: { emoji: "🔥", label: "Courage", desc: "Force · Résilience · Esprit du Guerrier" },
  clarity: { emoji: "👁",  label: "Clarté",  desc: "Vision · Discernement · Troisième Œil" },
};

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", display: "flex", flexDirection: "column", maxWidth: 640, margin: "0 auto", padding: "0 16px 32px" },
  header: { padding: "32px 0 24px", borderBottom: "1px solid #1a1730", marginBottom: 24 },
  logo: { fontSize: 32, marginBottom: 8, display: "block", textAlign: "center" },
  title: { fontFamily: "Cinzel, serif", fontSize: 28, fontWeight: 600, letterSpacing: "0.2em", textAlign: "center", color: "#c8b8f0", textTransform: "uppercase" as const },
  subtitle: { fontSize: 11, letterSpacing: "0.15em", textAlign: "center", color: "#4a4660", marginTop: 6, textTransform: "uppercase" as const },
  sectionLabel: { fontSize: 10, letterSpacing: "0.2em", color: "#4a4660", marginBottom: 12, textTransform: "uppercase" as const },
  cards: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 28 },
  card: { padding: "14px 8px", border: "1px solid #1a1730", borderRadius: 12, display: "flex", flexDirection: "column", alignItems: "center", gap: 6, background: "#0f0f1a", color: "#e8e0d0", transition: "all 0.2s", cursor: "pointer" },
  cardActive: { border: "1px solid #6c4ecb", background: "#130d25", boxShadow: "0 0 20px rgba(108,78,203,0.2)" },
  cardEmoji: { fontSize: 24 },
  cardLabel: { fontFamily: "Cinzel, serif", fontSize: 12, letterSpacing: "0.1em", color: "#c8b8f0" },
  cardDesc: { fontSize: 9, color: "#4a4660", textAlign: "center" as const, lineHeight: 1.5, letterSpacing: "0.05em" },
  chatBox: { border: "1px solid #1a1730", borderRadius: 16, background: "#0a0a14", marginBottom: 16, display: "flex", flexDirection: "column", height: 340, overflow: "hidden" },
  messages: { flex: 1, overflowY: "auto" as const, padding: 16, display: "flex", flexDirection: "column", gap: 12 },
  empty: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "#2a2040", fontSize: 13, textAlign: "center" as const, lineHeight: 1.8 },
  bubbleUser: { alignSelf: "flex-end", background: "#1a1030", borderRadius: "14px 14px 4px 14px", padding: "10px 14px", maxWidth: "80%", fontSize: 13, lineHeight: 1.6, color: "#c8b8f0" },
  bubbleAssistant: { alignSelf: "flex-start", background: "#0d1520", borderRadius: "4px 14px 14px 14px", padding: "10px 14px", maxWidth: "85%", fontSize: 13, lineHeight: 1.7, color: "#e8e0d0", border: "1px solid #1a2040" },
  priestTag: { fontSize: 9, letterSpacing: "0.15em", color: "#6c4ecb", display: "block", marginBottom: 4, textTransform: "uppercase" as const },
  inputRow: { display: "flex", gap: 8, padding: "12px 16px", borderTop: "1px solid #1a1730" },
  inputField: { flex: 1, background: "transparent", border: "none", color: "#e8e0d0", fontSize: 13, fontFamily: "Inter, sans-serif" },
  sendBtn: { width: 36, height: 36, borderRadius: "50%", background: "#6c4ecb", color: "#fff", fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, opacity: 1 },
  sendBtnDisabled: { opacity: 0.3 },
  proofSection: { marginTop: 8 },
  proofRow: { display: "flex", gap: 8 },
  proofInput: { flex: 1, background: "#0f0f1a", border: "1px solid #1a1730", borderRadius: 10, color: "#e8e0d0", fontSize: 12, padding: "10px 14px", fontFamily: "monospace" },
  proofBtn: { padding: "10px 18px", background: "#6c4ecb", borderRadius: 10, color: "#fff", fontSize: 12, letterSpacing: "0.05em", whiteSpace: "nowrap" as const },
  footer: { marginTop: "auto", paddingTop: 32, textAlign: "center" as const, fontSize: 10, color: "#2a2040", letterSpacing: "0.15em", textTransform: "uppercase" as const },
};

export default function App() {
  const [blessing, setBlessing] = useState<BlessingType>("flow");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [proofHash, setProofHash] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const callPriest = async (text: string, history: Message[]) => {
    setLoading(true);
    try {
      const res = await fetch("/api/priest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history, blessing }),
      });
      const data = await res.json();
      return data.text as string;
    } catch {
      return "🌊 Le portail est silencieux. Réessaie.";
    } finally {
      setLoading(false);
    }
  };

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const updated: Message[] = [...messages, { role: "user", content: text }];
    setMessages(updated);
    setInput("");
    const reply = await callPriest(text, messages);
    setMessages([...updated, { role: "assistant", content: reply }]);
  };

  const submitProof = async () => {
    if (!proofHash.trim() || loading) return;
    const text = `/proof ${proofHash.trim()} ${blessing}`;
    setProofHash("");
    await sendMessage(text);
  };

  return (
    <div style={s.page}>
      <header style={s.header}>
        <span style={s.logo}>⚡</span>
        <h1 style={s.title}>ALAGBARA</h1>
        <p style={s.subtitle}>Portal des Bénédictions · TON Blockchain</p>
      </header>

      <p style={s.sectionLabel}>Ta Voie</p>
      <div style={s.cards}>
        {(Object.keys(BLESSINGS) as BlessingType[]).map((b) => (
          <button key={b} onClick={() => setBlessing(b)} style={{ ...s.card, ...(blessing === b ? s.cardActive : {}) }}>
            <span style={s.cardEmoji}>{BLESSINGS[b].emoji}</span>
            <span style={s.cardLabel}>{BLESSINGS[b].label}</span>
            <span style={s.cardDesc}>{BLESSINGS[b].desc}</span>
          </button>
        ))}
      </div>

      <p style={s.sectionLabel}>Parler au Prêtre</p>
      <div style={s.chatBox}>
        <div style={s.messages}>
          {messages.length === 0 && !loading && (
            <div style={s.empty}>
              Le Prêtre ALAGBARA t'attend.<br />
              Parle ou soumets ta preuve de transaction.
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={m.role === "user" ? s.bubbleUser : s.bubbleAssistant}>
              {m.role === "assistant" && <span style={s.priestTag}>⚡ Prêtre Alagbara</span>}
              <span>{m.content}</span>
            </div>
          ))}
          {loading && (
            <div style={s.bubbleAssistant}>
              <span style={s.priestTag}>⚡ Prêtre Alagbara</span>
              <span style={{ color: "#3a3060" }}>🌊 &nbsp;·&nbsp;·&nbsp;·</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <div style={s.inputRow}>
          <input
            style={s.inputField}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
            placeholder="Écris au Prêtre..."
            disabled={loading}
          />
          <button
            style={{ ...s.sendBtn, ...(loading ? s.sendBtnDisabled : {}) }}
            onClick={() => sendMessage(input)}
            disabled={loading}
          >→</button>
        </div>
      </div>

      <div style={s.proofSection}>
        <p style={{ ...s.sectionLabel, marginBottom: 10 }}>Soumettre une Preuve TON</p>
        <div style={s.proofRow}>
          <input
            style={s.proofInput}
            value={proofHash}
            onChange={(e) => setProofHash(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitProof()}
            placeholder="Hash de transaction TON..."
            disabled={loading}
          />
          <button style={{ ...s.proofBtn, opacity: loading || !proofHash.trim() ? 0.4 : 1 }} onClick={submitProof} disabled={loading || !proofHash.trim()}>
            Soumettre
          </button>
        </div>
      </div>

      <footer style={s.footer}>
        <p>ALAGBARA · La Force · Yoruba</p>
      </footer>
    </div>
  );
}
