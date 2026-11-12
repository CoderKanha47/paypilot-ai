import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, Bot, User, Loader2, FileText, Lightbulb, Link2, Shield } from "lucide-react";
import { api, errorMessage } from "../lib/api";
import { useAsync } from "../hooks/useAsync";
import { useApp } from "../context/AppContext";
import { ModeBanner } from "../components/ModeBanner";
import type { ChatMessage, ChatResponse, AssistantSuggestionsResponse } from "../lib/types";

export function Assistant() {
  useApp();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const suggestions = useAsync(
    () => api.get<AssistantSuggestionsResponse>("/api/assistant/suggestions"),
    []
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = async (text: string) => {
    const question = text.trim();
    if (!question || busy) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setBusy(true);
    try {
      const res = await api.post<ChatResponse>("/api/assistant/chat", { message: question, history: messages });
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: res.answer,
        facts: res.facts,
        recommendations: res.recommendations,
        references: res.references,
        confidence: res.confidence,
        disclaimer: res.disclaimer,
      }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: `Sorry — ${errorMessage(err)}.` }]);
    } finally {
      setBusy(false);
    }
  };

  const renderAssistantMessage = (m: ChatMessage) => (
    <div className="flex gap-3">
      <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent">
        <Bot size={15} />
      </span>
      <div className="max-w-[80%] rounded-2xl bg-navy-100 px-4 py-3 text-sm text-ink">
        <p className="whitespace-pre-wrap">{m.content}</p>
        {m.facts && m.facts.length > 0 && (
          <div className="mt-3 space-y-1.5 border-t border-navy-700/15 pt-3">
            <div className="flex items-center gap-1.5 text-xs font-medium text-accent">
              <FileText size={12} /> Facts
            </div>
            <ul className="ml-4 space-y-1 list-disc text-muted">
              {m.facts.map((fact, i) => (
                <li key={i} className="text-sm">{fact}</li>
              ))}
            </ul>
          </div>
        )}
        {m.recommendations && m.recommendations.length > 0 && (
          <div className="mt-3 space-y-1.5 border-t border-navy-700/15 pt-3">
            <div className="flex items-center gap-1.5 text-xs font-medium text-warning">
              <Lightbulb size={12} /> Recommendations
            </div>
            <ul className="ml-4 space-y-1 list-disc text-muted">
              {m.recommendations.map((rec, i) => (
                <li key={i} className="text-sm">{rec}</li>
              ))}
            </ul>
          </div>
        )}
        {m.references && m.references.length > 0 && (
          <div className="mt-3 space-y-1.5 border-t border-navy-700/15 pt-3">
            <div className="flex items-center gap-1.5 text-xs font-medium text-info">
              <Link2 size={12} /> Transaction References
            </div>
            <ul className="ml-4 space-y-1 list-disc text-muted">
              {m.references.map((ref, i) => (
                <li key={i} className="text-sm">
                  <a
                    href={`/transactions/${ref}`}
                    className="text-info hover:underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {ref}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
        {m.confidence && (
          <div className="mt-2 flex items-center gap-2 text-xs text-faint">
            <Shield size={12} /> Confidence: <span className="font-medium capitalize">{m.confidence}</span>
          </div>
        )}
        {m.disclaimer && (
          <p className="mt-2 text-xs text-faint italic">{m.disclaimer}</p>
        )}
      </div>
    </div>
  );

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-4xl flex-col">
      <div className="mb-4 flex items-center gap-2">
        <Sparkles size={18} className="text-accent" />
        <h1 className="text-xl font-semibold">AI Payment Analyst</h1>
      </div>

      <ModeBanner />

      <div className="card mt-3 flex-1 space-y-4 overflow-y-auto p-5">
        {messages.length === 0 && (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              I read real aggregates from your payment database and hand arithmetic to the backend, so my numbers are
              always grounded. Try one of these:
            </p>
            <div className="flex flex-wrap gap-2">
              {(suggestions.data?.suggestions ?? []).map((s) => (
                <button key={s} className="btn btn-ghost text-sm" onClick={() => void send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === "user" ? "justify-end" : ""}`}>
            {m.role === "assistant" ? (
              renderAssistantMessage(m)
            ) : (
              <>
                <div className="max-w-[80%] rounded-2xl bg-navy-900 px-4 py-2.5 text-sm text-ink">
                  <p className="whitespace-pre-wrap">{m.content}</p>
                </div>
                <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-navy-700/15 text-muted">
                  <User size={15} />
                </span>
              </>
            )}
          </div>
        ))}

        {busy && (
          <div className="flex gap-3">
            <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/15 text-accent">
              <Bot size={15} />
            </span>
            <div className="rounded-2xl bg-navy-100 px-4 py-3 text-sm text-muted">
              <Loader2 size={14} className="animate-spin mx-auto" aria-hidden="true" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <input
          className="input flex-1"
          placeholder="Ask about your payments…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={500}
        />
        <button className="btn btn-primary inline-flex items-center gap-2" disabled={busy || !input.trim()}>
          <Send size={15} /> Ask
        </button>
      </form>
      <p className="mt-2 text-xs text-faint">
        Answers are grounded in your data; money math is computed in integer cents by the backend, never by the model.
      </p>
    </div>
  );
}