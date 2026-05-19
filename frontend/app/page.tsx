"use client";

import { useState, useRef, FormEvent } from "react";

// ── Types ────────────────────────────────────────────────────────────────────

interface VideoSearched {
  id: string;
  title: string;
  duration: number;
}

interface CostBreakdown {
  input_tokens: number;
  output_tokens: number;
  total_usd: number;
  total_jpy: number;
}

interface QueryResponse {
  answer: string;
  videos_searched: VideoSearched[];
  types_in_brief: string[];
  knowledge_objects_used: number;
  context_tokens: number;
  cost: CostBreakdown;
  cached: boolean;
}

interface KnowledgeObject {
  id: string;
  type: string;
  content: string;
  entities: string[];
  confidence: number;
  video_id: string;
  timestamp: number;
}

type Stage =
  | "idle"
  | "searching"
  | "extracting"
  | "ranking"
  | "answering"
  | "done"
  | "error";

const STAGE_LABELS: Record<Stage, string> = {
  idle: "",
  searching: "Searching YouTube...",
  extracting: "Extracting knowledge objects...",
  ranking: "Ranking & assembling brief...",
  answering: "Generating answer with Claude Sonnet...",
  done: "Done",
  error: "Error",
};

const TYPE_COLORS: Record<string, string> = {
  claim: "#6366f1",
  procedure: "#10b981",
  comparison: "#f59e0b",
  constraint: "#ef4444",
  risk: "#f97316",
  metric: "#3b82f6",
  principle: "#8b5cf6",
  relationship: "#06b6d4",
  definition: "#84cc16",
  example: "#ec4899",
};

// ── Sub-components ────────────────────────────────────────────────────────────

function TypeBadge({ type }: { type: string }) {
  const color = TYPE_COLORS[type] ?? "#6b7280";
  return (
    <span
      style={{
        backgroundColor: color + "22",
        color: color,
        border: `1px solid ${color}44`,
        padding: "2px 8px",
        borderRadius: "4px",
        fontSize: "11px",
        fontWeight: 600,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        fontFamily: "inherit",
      }}
    >
      {type}
    </span>
  );
}

function StagePipeline({ stage }: { stage: Stage }) {
  const stages: Stage[] = ["searching", "extracting", "ranking", "answering"];
  const currentIdx = stages.indexOf(stage);

  if (stage === "idle" || stage === "done") return null;

  return (
    <div style={{ marginBottom: "24px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flexWrap: "wrap",
        }}
      >
        {stages.map((s, i) => {
          const isActive = i === currentIdx;
          const isDone = i < currentIdx;
          const isPending = i > currentIdx;
          return (
            <div key={s} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "6px 12px",
                  borderRadius: "6px",
                  border: `1px solid ${isActive ? "#6366f1" : isDone ? "#374151" : "#1f2937"}`,
                  backgroundColor: isActive
                    ? "#6366f122"
                    : isDone
                    ? "#111111"
                    : "transparent",
                  fontSize: "12px",
                  color: isActive ? "#818cf8" : isDone ? "#6b7280" : "#374151",
                  fontFamily: "inherit",
                }}
              >
                {isDone && (
                  <span style={{ color: "#10b981", fontSize: "10px" }}>✓</span>
                )}
                {isActive && (
                  <span
                    style={{
                      display: "inline-block",
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      backgroundColor: "#6366f1",
                      animation: "pulse 1s infinite",
                    }}
                  />
                )}
                {STAGE_LABELS[s]}
              </div>
              {i < stages.length - 1 && (
                <span style={{ color: "#374151", fontSize: "10px" }}>→</span>
              )}
            </div>
          );
        })}
      </div>
      {stage === "error" && (
        <p style={{ color: "#ef4444", marginTop: "8px", fontSize: "13px" }}>
          {STAGE_LABELS.error}
        </p>
      )}
    </div>
  );
}

function VideoCard({ video }: { video: VideoSearched }) {
  const mins = Math.floor(video.duration / 60);
  const secs = video.duration % 60;
  return (
    <a
      href={`https://youtube.com/watch?v=${video.id}`}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "block",
        padding: "10px 14px",
        border: "1px solid #2a2a2a",
        borderRadius: "6px",
        backgroundColor: "#111111",
        textDecoration: "none",
        color: "inherit",
        fontSize: "12px",
        cursor: "pointer",
      }}
    >
      <div style={{ color: "#f9fafb", fontWeight: 500, marginBottom: "2px", lineHeight: 1.4 }}>
        {video.title}
      </div>
      <div style={{ color: "#6b7280", fontSize: "11px" }}>
        {video.id} · {mins}m{secs.toString().padStart(2, "0")}s
      </div>
    </a>
  );
}

function KnowledgeBriefPanel({
  objectsByType,
}: {
  objectsByType: Record<string, KnowledgeObject[]>;
}) {
  const [open, setOpen] = useState(false);
  const types = Object.keys(objectsByType);
  if (types.length === 0) return null;

  return (
    <div
      style={{
        border: "1px solid #2a2a2a",
        borderRadius: "8px",
        overflow: "hidden",
        marginTop: "24px",
      }}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%",
          padding: "14px 18px",
          backgroundColor: "#1a1a1a",
          border: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          color: "#f9fafb",
          fontSize: "13px",
          fontFamily: "inherit",
          fontWeight: 600,
        }}
      >
        <span>Knowledge Brief</span>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
            {types.map((t) => (
              <TypeBadge key={t} type={t} />
            ))}
          </div>
          <span style={{ color: "#6b7280", fontSize: "16px" }}>
            {open ? "▲" : "▼"}
          </span>
        </div>
      </button>

      {open && (
        <div style={{ backgroundColor: "#0f0f0f", padding: "18px" }}>
          {types.map((ktype) => {
            const objects = objectsByType[ktype];
            const color = TYPE_COLORS[ktype] ?? "#6b7280";
            return (
              <div key={ktype} style={{ marginBottom: "20px" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: "10px",
                  }}
                >
                  <div
                    style={{
                      width: "3px",
                      height: "16px",
                      backgroundColor: color,
                      borderRadius: "2px",
                      flexShrink: 0,
                    }}
                  />
                  <TypeBadge type={ktype} />
                  <span style={{ color: "#6b7280", fontSize: "11px" }}>
                    {objects.length} object{objects.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {objects.map((obj) => (
                    <div
                      key={obj.id}
                      style={{
                        padding: "10px 14px",
                        backgroundColor: "#1a1a1a",
                        borderRadius: "6px",
                        borderLeft: `3px solid ${color}66`,
                        fontSize: "12px",
                        lineHeight: 1.6,
                      }}
                    >
                      <div style={{ color: "#e5e7eb", marginBottom: "4px" }}>
                        {obj.content}
                      </div>
                      <div
                        style={{
                          display: "flex",
                          gap: "8px",
                          fontSize: "10px",
                          color: "#6b7280",
                          flexWrap: "wrap",
                        }}
                      >
                        <span>[{Math.round(obj.timestamp)}s]</span>
                        <span>conf: {obj.confidence.toFixed(2)}</span>
                        {obj.entities.length > 0 && (
                          <span>{obj.entities.slice(0, 4).join(", ")}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function Home() {
  const [query, setQuery] = useState("");
  const [maxVideos, setMaxVideos] = useState(3);
  const [stage, setStage] = useState<Stage>("idle");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [objectsByType, setObjectsByType] = useState<
    Record<string, KnowledgeObject[]>
  >({});
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!query.trim() || stage !== "idle") return;

    setResult(null);
    setErrorMsg("");
    setObjectsByType({});

    // Simulate pipeline stage progression while waiting for the API
    setStage("searching");

    const stageTimer1 = setTimeout(() => setStage("extracting"), 2000);
    const stageTimer2 = setTimeout(() => setStage("ranking"), 5000);
    const stageTimer3 = setTimeout(() => setStage("answering"), 7000);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), max_videos: maxVideos }),
      });

      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(data.detail ?? res.statusText);
      }

      const data: QueryResponse = await res.json();
      setResult(data);
      setStage("done");

      // Fetch knowledge objects from each video for the brief panel
      const byType: Record<string, KnowledgeObject[]> = {};
      for (const video of data.videos_searched) {
        try {
          const kr = await fetch(`/api/knowledge/${video.id}`);
          if (kr.ok) {
            const kd = await kr.json();
            for (const [t, objs] of Object.entries(
              kd.objects_by_type as Record<string, KnowledgeObject[]>
            )) {
              if (data.types_in_brief.includes(t)) {
                byType[t] = [...(byType[t] ?? []), ...objs];
              }
            }
          }
        } catch {
          // non-fatal — brief panel just won't show this video's objects
        }
      }
      setObjectsByType(byType);
    } catch (err: unknown) {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      clearTimeout(stageTimer3);
      setStage("error");
      setErrorMsg(err instanceof Error ? err.message : String(err));
    }
  }

  function handleReset() {
    setStage("idle");
    setResult(null);
    setErrorMsg("");
    setObjectsByType({});
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  const isLoading =
    stage === "searching" ||
    stage === "extracting" ||
    stage === "ranking" ||
    stage === "answering";

  return (
    <main
      style={{
        minHeight: "100vh",
        backgroundColor: "#0a0a0a",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "48px 16px 80px",
      }}
    >
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: "48px" }}>
        <h1
          style={{
            fontSize: "clamp(22px, 4vw, 32px)",
            fontWeight: 700,
            color: "#f9fafb",
            letterSpacing: "-0.02em",
            marginBottom: "8px",
            fontFamily: "inherit",
          }}
        >
          Context Engine
        </h1>
        <p
          style={{
            color: "#6b7280",
            fontSize: "13px",
            fontFamily: "inherit",
          }}
        >
          YouTube knowledge extraction · structured AI reasoning
        </p>
      </div>

      {/* Search form */}
      <div style={{ width: "100%", maxWidth: "760px" }}>
        <form onSubmit={handleSubmit}>
          <div
            style={{
              display: "flex",
              gap: "8px",
              alignItems: "stretch",
              marginBottom: "12px",
            }}
          >
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask anything... e.g. Claude Code token optimization"
              disabled={isLoading}
              autoFocus
              style={{
                flex: 1,
                padding: "14px 18px",
                backgroundColor: "#111111",
                border: `1px solid ${isLoading ? "#2a2a2a" : "#374151"}`,
                borderRadius: "8px",
                color: "#f9fafb",
                fontSize: "15px",
                fontFamily: "inherit",
                outline: "none",
                caretColor: "#6366f1",
                opacity: isLoading ? 0.6 : 1,
              }}
              onFocus={(e) => {
                if (!isLoading)
                  e.currentTarget.style.borderColor = "#6366f1";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderColor = "#374151";
              }}
            />
            <button
              type="submit"
              disabled={isLoading || !query.trim()}
              style={{
                padding: "14px 24px",
                backgroundColor: isLoading || !query.trim() ? "#1f2937" : "#6366f1",
                border: "none",
                borderRadius: "8px",
                color: isLoading || !query.trim() ? "#6b7280" : "#fff",
                fontSize: "14px",
                fontWeight: 600,
                fontFamily: "inherit",
                cursor: isLoading || !query.trim() ? "not-allowed" : "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {isLoading ? "..." : "Search"}
            </button>
          </div>

          {/* Options row */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "16px",
              fontSize: "12px",
              color: "#6b7280",
            }}
          >
            <label style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span>Videos to search:</span>
              {[1, 2, 3, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setMaxVideos(n)}
                  disabled={isLoading}
                  style={{
                    padding: "2px 10px",
                    borderRadius: "4px",
                    border: `1px solid ${maxVideos === n ? "#6366f1" : "#2a2a2a"}`,
                    backgroundColor: maxVideos === n ? "#6366f122" : "transparent",
                    color: maxVideos === n ? "#818cf8" : "#6b7280",
                    fontSize: "12px",
                    fontFamily: "inherit",
                    cursor: isLoading ? "not-allowed" : "pointer",
                  }}
                >
                  {n}
                </button>
              ))}
            </label>
          </div>
        </form>

        {/* Pipeline stage indicator */}
        {stage !== "idle" && stage !== "done" && stage !== "error" && (
          <div style={{ marginTop: "28px" }}>
            <StagePipeline stage={stage} />
          </div>
        )}

        {/* Error message */}
        {stage === "error" && (
          <div
            style={{
              marginTop: "24px",
              padding: "16px 20px",
              backgroundColor: "#ef444411",
              border: "1px solid #ef444433",
              borderRadius: "8px",
              color: "#fca5a5",
              fontSize: "13px",
              lineHeight: 1.6,
            }}
          >
            <strong style={{ display: "block", marginBottom: "4px" }}>
              Something went wrong
            </strong>
            {errorMsg}
            <button
              onClick={handleReset}
              style={{
                display: "block",
                marginTop: "12px",
                padding: "6px 16px",
                backgroundColor: "transparent",
                border: "1px solid #ef444466",
                borderRadius: "4px",
                color: "#fca5a5",
                fontSize: "12px",
                fontFamily: "inherit",
                cursor: "pointer",
              }}
            >
              Try again
            </button>
          </div>
        )}

        {/* Result */}
        {result && stage === "done" && (
          <div style={{ marginTop: "32px" }}>
            {/* Videos used */}
            {result.videos_searched.length > 0 && (
              <div style={{ marginBottom: "20px" }}>
                <div
                  style={{
                    fontSize: "11px",
                    color: "#6b7280",
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    marginBottom: "8px",
                  }}
                >
                  Sources ({result.videos_searched.length})
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {result.videos_searched.map((v) => (
                    <VideoCard key={v.id} video={v} />
                  ))}
                </div>
              </div>
            )}

            {/* Answer */}
            <div
              style={{
                padding: "24px 28px",
                backgroundColor: "#111111",
                border: "1px solid #2a2a2a",
                borderRadius: "10px",
                marginBottom: "0",
              }}
            >
              <div
                style={{
                  fontSize: "11px",
                  color: "#6b7280",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  marginBottom: "16px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <span>Answer</span>
                {result.cached && (
                  <span
                    style={{
                      padding: "1px 8px",
                      backgroundColor: "#10b98122",
                      color: "#10b981",
                      borderRadius: "3px",
                      fontSize: "10px",
                    }}
                  >
                    cached
                  </span>
                )}
              </div>
              <div
                style={{
                  color: "#f3f4f6",
                  fontSize: "15px",
                  lineHeight: 1.75,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {result.answer}
              </div>
            </div>

            {/* Knowledge brief (collapsible) */}
            {Object.keys(objectsByType).length > 0 && (
              <KnowledgeBriefPanel objectsByType={objectsByType} />
            )}

            {/* Stats footer */}
            <div
              style={{
                marginTop: "16px",
                display: "flex",
                alignItems: "center",
                gap: "16px",
                flexWrap: "wrap",
                fontSize: "11px",
                color: "#6b7280",
                padding: "10px 4px",
                borderTop: "1px solid #1f2937",
              }}
            >
              <span>
                {result.knowledge_objects_used} object
                {result.knowledge_objects_used !== 1 ? "s" : ""}
              </span>
              <span>·</span>
              <div style={{ display: "flex", gap: "4px" }}>
                {result.types_in_brief.map((t) => (
                  <TypeBadge key={t} type={t} />
                ))}
              </div>
              <span>·</span>
              <span>{result.context_tokens.toLocaleString()} tokens</span>
              <span>·</span>
              <span>¥{result.cost.total_jpy.toFixed(2)}</span>
              <div style={{ marginLeft: "auto" }}>
                <button
                  onClick={handleReset}
                  style={{
                    padding: "4px 14px",
                    backgroundColor: "transparent",
                    border: "1px solid #2a2a2a",
                    borderRadius: "4px",
                    color: "#6b7280",
                    fontSize: "11px",
                    fontFamily: "inherit",
                    cursor: "pointer",
                  }}
                >
                  New search
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </main>
  );
}
