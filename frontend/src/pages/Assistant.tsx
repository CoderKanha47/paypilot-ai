import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, Bot, User, Loader2 } from "lucide-react";
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
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: `Sorry — ${errorMessage(err)}.` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] max-w-4xl flex-col">
      <div className="mb-4 flex items-center gap-2">
        <Sparkles size={18} className="text-violet-600" />
        <h1 className="text-xl font-semibold">AI Payment Analyst</h1>
      </div>

      <ModeBanner />

      <div className="card mt-3 flex-1 space-y-4 overflow-y-auto p-5">
        {messages.length === 0 && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
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
            {m.role === "assistant" && (
              <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-100 text-violet-700">
                <Bot size={15} />
              </span>
            )}
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${m.role === "user" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-800"}`}>
              <p className="whitespace-pre-wrap">{m.content}</p>
            </div>
            {m.role === "user" && (
              <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600">
                <User size={15} />
              </span>
            )}
          </div>
        ))}

        {busy && (
          <div className="flex gap-3">
            <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-100 text-violet-700">
              <Bot size={15} />
            </span>
            <div className="rounded-2xl bg-slate-100 px-4 py-3 text-sm text-slate-500">
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
      <p className="mt-2 text-xs text-slate-500">
        Answers are grounded in your data; money math is computed in integer cents by the backend, never by the model.
      </p>
    </div>
  );
}