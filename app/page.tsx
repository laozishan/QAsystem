"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Bot, FileText, Globe2, Loader2, Plus, Send, Trash2, Upload } from "lucide-react";
import { API_BASE, Citation, DocumentItem, fetchDocuments } from "../lib/api";

type Message = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
};

export default function Home() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [webUrl, setWebUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement | null>(null);

  const activeDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocument),
    [documents, selectedDocument],
  );

  async function refreshDocuments() {
    const items = await fetchDocuments();
    setDocuments(items);
    if (!selectedDocument && items[0]) setSelectedDocument(items[0].id);
  }

  useEffect(() => {
    refreshDocuments().catch((err) => setError(err.message));
  }, []);

  async function uploadFile(file: File) {
    setUploading(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    try {
      const response = await fetch(`${API_BASE}/api/documents/upload`, {
        method: "POST",
        body: form,
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Upload failed");
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function ingestWeb(event: FormEvent) {
    event.preventDefault();
    if (!webUrl.trim()) return;
    setUploading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/api/documents/web`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: webUrl.trim() }),
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Web ingest failed");
      setWebUrl("");
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Web ingest failed");
    } finally {
      setUploading(false);
    }
  }

  async function deleteDocument(id: string) {
    setError("");
    await fetch(`${API_BASE}/api/documents/${id}`, { method: "DELETE" });
    if (selectedDocument === id) setSelectedDocument("");
    await refreshDocuments();
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || busy) return;
    setQuestion("");
    setBusy(true);
    setError("");
    setMessages((current) => [...current, { role: "user", content: text }, { role: "assistant", content: "" }]);

    try {
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          conversation_id: conversationId,
          document_id: selectedDocument || undefined,
        }),
      });
      if (!response.ok || !response.body) throw new Error("Chat request failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let citations: Citation[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";
        for (const eventBlock of events) {
          const eventName = eventBlock.match(/^event: (.+)$/m)?.[1];
          const dataLine = eventBlock.match(/^data: (.+)$/m)?.[1];
          if (!dataLine) continue;
          const data = JSON.parse(dataLine);
          if (eventName === "meta") {
            setConversationId(data.conversation_id);
            citations = data.citations || [];
            setMessages((current) => {
              const copy = [...current];
              copy[copy.length - 1] = { ...copy[copy.length - 1], citations };
              return copy;
            });
          }
          if (eventName === "token") {
            setMessages((current) => {
              const copy = [...current];
              const last = copy[copy.length - 1];
              copy[copy.length - 1] = { ...last, content: last.content + data.token, citations };
              return copy;
            });
          }
          if (eventName === "error") {
            setError(data.message || "Answer generation failed");
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-mist text-ink">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-4 lg:px-6">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-normal">AI Knowledge QA</h1>
            <p className="mt-1 text-sm text-slate-600">RAG workspace for documents, web pages, and cited answers.</p>
          </div>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md bg-brand px-4 text-sm font-medium text-white disabled:opacity-60"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            title="Upload document"
          >
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Upload
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.txt,.md,.markdown"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) uploadFile(file);
              event.currentTarget.value = "";
            }}
          />
        </header>

        {error && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        )}

        <section className="grid flex-1 gap-4 py-4 lg:grid-cols-[330px_minmax(0,1fr)]">
          <aside className="flex min-h-[520px] flex-col rounded-md border border-line bg-white">
            <div className="border-b border-line p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase text-slate-500">Knowledge base</h2>
                <button
                  className="grid h-9 w-9 place-items-center rounded-md border border-line text-slate-700 hover:bg-mist"
                  onClick={() => fileRef.current?.click()}
                  title="Add file"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
              <form className="flex gap-2" onSubmit={ingestWeb}>
                <input
                  className="h-10 min-w-0 flex-1 rounded-md border border-line px-3 text-sm outline-none focus:border-brand"
                  placeholder="https://example.com/article"
                  value={webUrl}
                  onChange={(event) => setWebUrl(event.target.value)}
                />
                <button
                  className="grid h-10 w-10 place-items-center rounded-md bg-accent text-white disabled:opacity-60"
                  disabled={uploading}
                  title="Add web page"
                >
                  <Globe2 className="h-4 w-4" />
                </button>
              </form>
            </div>

            <div className="scrollbar-thin flex-1 overflow-auto p-2">
              {documents.length === 0 ? (
                <div className="grid h-full place-items-center px-6 text-center text-sm text-slate-500">
                  Upload a document or add a web page to start.
                </div>
              ) : (
                documents.map((document) => (
                  <div
                    key={document.id}
                    className={`mb-2 rounded-md border p-3 ${
                      selectedDocument === document.id ? "border-brand bg-emerald-50" : "border-line bg-white"
                    }`}
                  >
                    <button
                      className="flex w-full items-start gap-3 text-left"
                      onClick={() => setSelectedDocument(document.id)}
                    >
                      <FileText className="mt-1 h-4 w-4 shrink-0 text-brand" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{document.title}</span>
                        <span className="block truncate text-xs text-slate-500">{document.source}</span>
                      </span>
                    </button>
                    <button
                      className="mt-2 inline-flex h-8 items-center gap-1 rounded-md px-2 text-xs text-slate-500 hover:bg-white hover:text-red-600"
                      onClick={() => deleteDocument(document.id)}
                      title="Delete document"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </button>
                  </div>
                ))
              )}
            </div>
          </aside>

          <section className="flex min-h-[520px] flex-col rounded-md border border-line bg-white">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="min-w-0">
                <h2 className="truncate text-base font-semibold">{activeDocument?.title || "All documents"}</h2>
                <p className="truncate text-xs text-slate-500">{activeDocument?.source || "Search the full knowledge base"}</p>
              </div>
              <Bot className="h-5 w-5 text-brand" />
            </div>

            <div className="scrollbar-thin flex-1 overflow-auto p-4">
              {messages.length === 0 ? (
                <div className="grid h-full place-items-center text-center text-sm text-slate-500">
                  Ask a question about the selected knowledge base.
                </div>
              ) : (
                <div className="space-y-4">
                  {messages.map((message, index) => (
                    <article
                      key={index}
                      className={`max-w-[900px] rounded-md border px-4 py-3 ${
                        message.role === "user"
                          ? "ml-auto border-brand bg-emerald-50"
                          : "mr-auto border-line bg-mist"
                      }`}
                    >
                      <div className="whitespace-pre-wrap text-sm leading-6">{message.content || "..."}</div>
                      {message.role === "assistant" && message.citations && message.citations.length > 0 && (
                        <div className="mt-3 border-t border-line pt-3">
                          <div className="mb-2 text-xs font-semibold uppercase text-slate-500">Sources</div>
                          <div className="grid gap-2">
                            {message.citations.slice(0, 3).map((citation) => (
                              <div key={`${citation.rank}-${citation.chunk_index}`} className="rounded-md bg-white p-2 text-xs">
                                <div className="font-medium">
                                  [{citation.rank}] {citation.title}
                                </div>
                                <p className="mt-1 line-clamp-2 text-slate-600">{citation.text}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </div>

            <form className="border-t border-line p-3" onSubmit={ask}>
              <div className="flex gap-2">
                <textarea
                  className="min-h-12 max-h-36 flex-1 resize-y rounded-md border border-line px-3 py-3 text-sm outline-none focus:border-brand"
                  placeholder="Ask, summarize, compare, or follow up..."
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                />
                <button
                  className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-brand text-white disabled:opacity-60"
                  disabled={busy || !question.trim()}
                  title="Send"
                >
                  {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Send className="h-5 w-5" />}
                </button>
              </div>
            </form>
          </section>
        </section>
      </div>
    </main>
  );
}
