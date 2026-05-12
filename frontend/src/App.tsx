import { useMemo, useState } from "react";
import ReactFlow, { Background, Controls, Edge, MarkerType, Node } from "reactflow";
import { Activity, AlertTriangle, Database, GitBranch, Play, Search, UploadCloud } from "lucide-react";

const API_BASE = "http://localhost:8000";

type Evidence = {
  chunk_id: string;
  title: string;
  source: string;
  text: string;
  score: number;
  hazards: string[];
  locations: string[];
  evaluator: string;
};

type Anomaly = {
  id: string;
  severity: string;
  score: number;
  reason: string;
  evidence: string;
  node_id?: string;
};

type QueryResponse = {
  answer: string;
  router: Record<string, number>;
  retrieval_budget: Record<string, number>;
  evidences: Evidence[];
  graph: { nodes: Array<{ id: string; label: string; type: string; score: number }>; edges: Array<{ source: string; target: string; label: string; weight: number }> };
  anomalies: Anomaly[];
  pipeline: Array<{ id: string; label: string; status: string; detail?: unknown }>;
};

const sampleText =
  "2025年08月12日於高雄山區累積雨量達620mm，低窪區域淹水，道路排水不足。\\n\\n在六龜附近邊坡監測到滑動位移12cm，土石流潛勢溪流警戒提高。雖初報稱無災損，但後續表格記錄一座便橋沖毀並造成交通中斷。";

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function pipelineElements(result?: QueryResponse): { nodes: Node[]; edges: Edge[] } {
  const steps = result?.pipeline ?? [
    { id: "query", label: "Query", status: "idle" },
    { id: "router", label: "MoR Router", status: "idle" },
    { id: "retrieval", label: "Hybrid Retrieval", status: "idle" },
    { id: "rerank", label: "Rerank", status: "idle" },
    { id: "evaluate", label: "Evidence Evaluator", status: "idle" },
    { id: "anomaly", label: "Graph Anomaly", status: "idle" },
    { id: "answer", label: "Answer", status: "idle" },
  ];
  const nodes = steps.map((step, index) => ({
    id: step.id,
    position: { x: index * 190, y: index % 2 === 0 ? 28 : 124 },
    data: { label: `${step.label}\\n${step.status}` },
    className: `flow-node ${step.status}`,
  }));
  const edges = steps.slice(1).map((step, index) => ({
    id: `${steps[index].id}-${step.id}`,
    source: steps[index].id,
    target: step.id,
    markerEnd: { type: MarkerType.ArrowClosed },
    animated: Boolean(result),
  }));
  return { nodes, edges };
}

function graphElements(result?: QueryResponse): { nodes: Node[]; edges: Edge[] } {
  if (!result) {
    return { nodes: [], edges: [] };
  }
  const angleStep = (Math.PI * 2) / Math.max(result.graph.nodes.length, 1);
  const anomalies = new Set(result.anomalies.map((item) => item.node_id).filter(Boolean));
  const nodes = result.graph.nodes.slice(0, 42).map((node, index) => ({
    id: node.id,
    position: { x: 360 + Math.cos(index * angleStep) * 280, y: 210 + Math.sin(index * angleStep) * 170 },
    data: { label: node.label },
    className: `graph-node ${node.type} ${anomalies.has(node.id) ? "anomaly" : ""}`,
  }));
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = result.graph.edges
    .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
    .slice(0, 70)
    .map((edge, index) => ({
      id: `g-${index}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      markerEnd: { type: MarkerType.ArrowClosed },
    }));
  return { nodes, edges };
}

export default function App() {
  const [title, setTitle] = useState("新進災害調查資料");
  const [source, setSource] = useState("manual-demo");
  const [text, setText] = useState(sampleText);
  const [query, setQuery] = useState("高雄豪雨造成哪些災害與異常？");
  const [result, setResult] = useState<QueryResponse>();
  const [message, setMessage] = useState("尚未查詢");
  const [loading, setLoading] = useState(false);

  const pipeline = useMemo(() => pipelineElements(result), [result]);
  const graph = useMemo(() => graphElements(result), [result]);

  async function seed() {
    setLoading(true);
    try {
      await postJson("/api/demo/seed");
      setMessage("已建立 demo 知識庫");
    } finally {
      setLoading(false);
    }
  }

  async function ingest() {
    setLoading(true);
    try {
      await postJson("/api/ingest", { title, source, text });
      setMessage("資料已匯入並完成 agentic chunking");
    } finally {
      setLoading(false);
    }
  }

  async function runQuery() {
    setLoading(true);
    try {
      const data = await postJson<QueryResponse>("/api/query", { query, top_k: 6 });
      setResult(data);
      setMessage("查詢完成");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Graph-enhanced MoRA-RAG MVP</p>
          <h1>災後調查知識庫與異常偵測操作台</h1>
        </div>
        <div className="status"><Activity size={16} />{message}</div>
      </header>

      <section className="workspace">
        <aside className="panel controls-panel">
          <div className="panel-title"><Database size={18} />資料匯入</div>
          <label>標題<input value={title} onChange={(event) => setTitle(event.target.value)} /></label>
          <label>來源<input value={source} onChange={(event) => setSource(event.target.value)} /></label>
          <label>調查文字<textarea value={text} onChange={(event) => setText(event.target.value)} rows={8} /></label>
          <div className="actions">
            <button onClick={seed} disabled={loading}><Play size={16} />Demo Seed</button>
            <button onClick={ingest} disabled={loading}><UploadCloud size={16} />匯入</button>
          </div>

          <div className="panel-title spaced"><Search size={18} />RAG 查詢</div>
          <label>Query<textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={3} /></label>
          <button className="primary" onClick={runQuery} disabled={loading}><Search size={16} />執行 MoR-RAG</button>
        </aside>

        <section className="main-grid">
          <div className="panel pipeline-panel">
            <div className="panel-title"><GitBranch size={18} />RAG Pipeline Trace</div>
            <ReactFlow nodes={pipeline.nodes} edges={pipeline.edges} fitView>
              <Background />
              <Controls />
            </ReactFlow>
          </div>

          <div className="panel graph-panel">
            <div className="panel-title"><GitBranch size={18} />Knowledge Graph</div>
            {graph.nodes.length ? (
              <ReactFlow nodes={graph.nodes} edges={graph.edges} fitView>
                <Background />
                <Controls />
              </ReactFlow>
            ) : (
              <div className="empty">執行查詢後顯示圖譜</div>
            )}
          </div>

          <div className="panel answer-panel">
            <div className="panel-title">回答與 Router</div>
            <p className="answer">{result?.answer ?? "建立 demo seed 後執行查詢，即可看到回答、證據與異常判定。"}</p>
            <div className="bars">
              {Object.entries(result?.router ?? {}).map(([key, value]) => (
                <div className="bar-row" key={key}>
                  <span>{key}</span>
                  <div><i style={{ width: `${value * 100}%` }} /></div>
                  <strong>{Math.round(value * 100)}%</strong>
                </div>
              ))}
            </div>
          </div>

          <div className="panel evidence-panel">
            <div className="panel-title">Evidence</div>
            <div className="evidence-list">
              {(result?.evidences ?? []).map((evidence) => (
                <article key={evidence.chunk_id}>
                  <header>
                    <strong>{evidence.title}</strong>
                    <span>{evidence.score.toFixed(3)} / {evidence.evaluator}</span>
                  </header>
                  <p>{evidence.text}</p>
                  <small>{evidence.hazards.join(", ")} · {evidence.locations.join(", ") || "no location"}</small>
                </article>
              ))}
            </div>
          </div>

          <div className="panel anomaly-panel">
            <div className="panel-title"><AlertTriangle size={18} />異常判定</div>
            <div className="anomaly-list">
              {(result?.anomalies ?? []).map((anomaly) => (
                <article key={anomaly.id} className={anomaly.severity}>
                  <header>
                    <strong>{anomaly.severity}</strong>
                    <span>{Math.round(anomaly.score * 100)}%</span>
                  </header>
                  <p>{anomaly.reason}</p>
                  <small>{anomaly.evidence}</small>
                </article>
              ))}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
