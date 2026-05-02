import { useEffect, useMemo, useState } from "react";
import { createNumber, createMarkdown, listRuntimes, runRuntime, traceObject, verifyObject } from "./lib/uar";
import { parseMarkdownToGraph } from "./lib/markdownParser";

type Node = {
  id: string;
  label: string;
  value: unknown;
  kind: string;
  x: number;
  y: number;
};

type Edge = {
  id: string;
  from: string;
  to: string;
  label: string;
};

function shortId(id: string) {
  return id.length > 18 ? `${id.slice(0, 12)}…` : id;
}

export default function App() {
  const [input, setInput] = useState("");
  const [markdownInput, setMarkdownInput] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [runtimes, setRuntimes] = useState<string[]>([]);
  const [activeRuntime, setActiveRuntime] = useState<string | null>(null);
  const [trace, setTrace] = useState<any>(null);
  const [verification, setVerification] = useState<Record<string, any>>({});
  const [dragging, setDragging] = useState<{ id: string; dx: number; dy: number } | null>(null);

  useEffect(() => {
    listRuntimes().then((r) => {
      const names = (r?.runtimes ?? []).map((x: any) => x.name);
      setRuntimes(names);
      setActiveRuntime(names[0] ?? null);
    }).catch(() => {});
  }, []);

  const selectedNodes = useMemo(() => nodes.filter((n) => selected.includes(n.id)), [nodes, selected]);

  const floatingPosition = useMemo(() => {
    if (!selectedNodes.length) return null;
    const x = selectedNodes.reduce((sum, n) => sum + n.x, 0) / selectedNodes.length;
    const y = selectedNodes.reduce((sum, n) => sum + n.y, 0) / selectedNodes.length;
    return { x, y: y - 56 };
  }, [selectedNodes]);

  async function onAdd() {
    if (!input.trim()) return;
    const obj = await createNumber(Number(input));
    setNodes((current) => [
      ...current,
      {
        ...obj,
        x: 80 + current.length * 28,
        y: 120 + current.length * 24,
      },
    ]);
    setInput("");
  }

  async function onLoadMarkdownFile(file: File | null) {
    if (!file) return;
    const allowed = file.name.endsWith(".md") || file.name.endsWith(".markdown") || file.name.endsWith(".txt");
    if (!allowed) {
      alert("Please choose a .md, .markdown, or .txt file.");
      return;
    }
    const text = await file.text();
    setFileName(file.name);
    setMarkdownInput(text);
  }

  async function onAddMarkdown() {
    if (!markdownInput.trim()) return;

    const parsed = parseMarkdownToGraph(markdownInput);
    const idMap = new Map<string, string>();
    const createdNodes: Node[] = [];
    const batchOffset = nodes.length * 18;

    for (const parsedNode of parsed.nodes) {
      if (parsedNode.kind === "number") {
        const obj = await createNumber(Number(parsedNode.value));
        idMap.set(parsedNode.localId, obj.id);
        createdNodes.push({
          ...obj,
          label: parsedNode.label,
          kind: "number",
          x: parsedNode.x + batchOffset,
          y: parsedNode.y,
        });
        continue;
      }

      if (parsedNode.kind === "runtime") {
        const id = `runtime:${String(parsedNode.value)}:${Date.now()}:${createdNodes.length}`;
        idMap.set(parsedNode.localId, id);
        createdNodes.push({
          id,
          label: parsedNode.label,
          value: parsedNode.value,
          kind: "runtime",
          x: parsedNode.x + batchOffset,
          y: parsedNode.y,
        });
        continue;
      }

      const obj = await createMarkdown(String(parsedNode.value), parsedNode.label);
      idMap.set(parsedNode.localId, obj.id);
      createdNodes.push({
        ...obj,
        label: parsedNode.label,
        kind: parsedNode.kind,
        x: parsedNode.x + batchOffset,
        y: parsedNode.y,
      });
    }

    const createdEdges: Edge[] = parsed.edges
      .map((edge) => {
        const from = idMap.get(edge.from);
        const to = idMap.get(edge.to);
        if (!from || !to) return null;
        return { id: `${from}-${to}`, from, to, label: edge.label };
      })
      .filter((edge): edge is Edge => edge !== null);

    setNodes((current) => [...current, ...createdNodes]);
    setEdges((current) => [...current, ...createdEdges]);
    setSelected(createdNodes.map((node) => node.id));
    setMarkdownInput("");
    setFileName(null);
  }

  async function onRun() {
    if (!activeRuntime || selected.length === 0) return;
    const runInputs = selected.filter((id) => !id.startsWith("runtime:"));
    if (runInputs.length === 0) return;
    const res = await runRuntime(activeRuntime, runInputs);
    const inputNodes = nodes.filter((n) => runInputs.includes(n.id));
    const centerX = inputNodes.length ? inputNodes.reduce((s, n) => s + n.x, 0) / inputNodes.length : 200;
    const maxY = inputNodes.length ? Math.max(...inputNodes.map((n) => n.y)) : 120;
    const newNode: Node = {
      id: res.output,
      label: "result",
      value: res.result,
      kind: "result",
      x: centerX,
      y: maxY + 140,
    };
    setNodes((current) => [...current, newNode]);
    setEdges((current) => [
      ...current,
      ...runInputs.map((id) => ({ id: `${id}-${res.output}`, from: id, to: res.output, label: activeRuntime })),
    ]);
    setSelected([res.output]);
  }

  async function onTrace() {
    if (!selected[0] || selected[0].startsWith("runtime:")) return;
    const t = await traceObject(selected[0]);
    setTrace(t);
  }

  async function runVerify(id: string) {
    if (id.startsWith("runtime:")) return;
    const res = await verifyObject(id);
    setVerification((current) => ({ ...current, [id]: res }));
  }

  function toggleSelect(id: string, multi = false) {
    setTrace(null);
    setSelected((current) => {
      if (!multi) return [id];
      return current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
    });
  }

  function onMouseMove(e: React.MouseEvent) {
    if (!dragging) return;
    setNodes((current) => current.map((n) => n.id === dragging.id ? { ...n, x: e.clientX - dragging.dx, y: e.clientY - dragging.dy } : n));
  }

  function nodeById(id: string) {
    return nodes.find((n) => n.id === id);
  }

  function Badge({ label, active, title }: { label: string; active?: boolean; title?: string }) {
    return (
      <span title={title} style={{ fontSize: 10, color: active ? "#137333" : "#9aa0a6", border: "1px solid #e0e0e0", borderRadius: 999, padding: "2px 6px", background: active ? "#e6f4ea" : "#f8fafd" }}>
        {active ? "✔" : "○"} {label}
      </span>
    );
  }

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "Inter, system-ui, sans-serif", color: "#202124" }} onMouseMove={onMouseMove} onMouseUp={() => setDragging(null)}>
      <aside style={{ width: 240, borderRight: "1px solid #e0e0e0", padding: 14, background: "#fafafa", overflowY: "auto" }}>
        <h3 style={{ marginTop: 0 }}>UAR</h3>
        <div style={{ display: "flex", gap: 6 }}>
          <input style={{ flex: 1 }} value={input} placeholder="number" onChange={(e) => setInput(e.target.value)} />
          <button onClick={onAdd}>Add</button>
        </div>
        <div style={{ marginTop: 12 }}>
          <label style={{ display: "block", fontSize: 12, color: "#5f6368", marginBottom: 4 }}>Markdown / text ingestion</label>
          <input
            type="file"
            accept=".md,.markdown,.txt,text/markdown,text/plain"
            onChange={(e) => onLoadMarkdownFile(e.target.files?.[0] ?? null)}
            style={{ width: "100%", fontSize: 12, marginBottom: 6 }}
          />
          {fileName && <div style={{ fontSize: 11, color: "#5f6368", marginBottom: 4 }}>Loaded: {fileName}</div>}
          <textarea
            value={markdownInput}
            placeholder={'Paste markdown or load a .md/.txt file...\nExample:\n5\n10\nsum'}
            onChange={(e) => setMarkdownInput(e.target.value)}
            style={{ width: "100%", height: 110, boxSizing: "border-box", resize: "vertical" }}
          />
          <button onClick={onAddMarkdown} style={{ marginTop: 6, width: "100%" }}>
            Parse Markdown to Graph
          </button>
        </div>
        <h4>Objects</h4>
        {nodes.map((n) => (
          <div key={n.id} onClick={() => toggleSelect(n.id)} style={{ padding: 8, marginBottom: 6, borderRadius: 8, cursor: "pointer", background: selected.includes(n.id) ? "#e8f0fe" : "#fff", border: "1px solid #eee" }}>
            <strong>{n.label}</strong>
            <div style={{ fontSize: 11, color: "#5f6368" }}>{n.kind} · {shortId(n.id)}</div>
          </div>
        ))}
      </aside>

      <main style={{ flex: 1, position: "relative", overflow: "hidden", background: "linear-gradient(#fff, #fff), radial-gradient(#e8eaed 1px, transparent 1px)", backgroundSize: "100% 100%, 24px 24px" }}>
        <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}>
          {edges.map((edge) => {
            const from = nodeById(edge.from);
            const to = nodeById(edge.to);
            if (!from || !to) return null;
            return (
              <g key={edge.id}>
                <line x1={from.x + 70} y1={from.y + 34} x2={to.x + 70} y2={to.y + 34} stroke="#9aa0a6" strokeWidth="2" />
                <text x={(from.x + to.x) / 2 + 70} y={(from.y + to.y) / 2 + 24} fontSize="11" fill="#5f6368">{edge.label}</text>
              </g>
            );
          })}
        </svg>

        {nodes.map((n) => (
          <div
            key={n.id}
            onMouseDown={(e) => setDragging({ id: n.id, dx: e.clientX - n.x, dy: e.clientY - n.y })}
            onClick={(e) => toggleSelect(n.id, e.shiftKey)}
            onDoubleClick={() => !n.id.startsWith("runtime:") && traceObject(n.id).then(setTrace)}
            style={{
              position: "absolute",
              left: n.x,
              top: n.y,
              width: 170,
              padding: 12,
              borderRadius: 14,
              background: n.kind === "result" ? "#eef2ff" : n.kind === "markdown" || n.kind === "text" ? "#fff8e1" : n.kind === "runtime" ? "#e8f0fe" : "#fff",
              border: selected.includes(n.id) ? "2px solid #1a73e8" : "1px solid #dadce0",
              boxShadow: "0 6px 18px rgba(60,64,67,0.12)",
              cursor: "grab",
              userSelect: "none",
            }}
          >
            <strong>{n.label}</strong>
            <div style={{ fontSize: 12, color: "#5f6368" }}>{n.kind}</div>
            <div style={{ fontSize: 10, color: "#80868b" }}>{shortId(n.id)}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
              <Badge label="hash" active={verification[n.id]?.valid === true || verification[n.id]?.verified === true} title="Integrity: hash verification" />
              <Badge label="replay n/a" title="Determinism replay is not wired yet" />
              <Badge label="proof n/a" title="Proof attachment is not wired yet" />
            </div>
          </div>
        ))}

        {floatingPosition && (
          <div style={{ position: "absolute", left: floatingPosition.x, top: floatingPosition.y, transform: "translateX(-20%)", display: "flex", gap: 8, alignItems: "center", padding: "8px 10px", borderRadius: 999, background: "#fff", border: "1px solid #dadce0", boxShadow: "0 8px 24px rgba(60,64,67,0.18)" }}>
            <select value={activeRuntime ?? ""} onChange={(e) => setActiveRuntime(e.target.value)}>
              {runtimes.map((r) => <option key={r}>{r}</option>)}
            </select>
            <button onClick={onRun}>Run</button>
            <button onClick={onTrace}>Trace</button>
            <button disabled={!selected[0] || selected[0].startsWith("runtime:")} onClick={() => selected[0] && runVerify(selected[0])}>Verify</button>
          </div>
        )}
      </main>

      <aside style={{ width: 320, borderLeft: "1px solid #e0e0e0", padding: 14, background: "#fff", overflowY: "auto" }}>
        <h4>Inspector</h4>
        {selected[0] ? <div style={{ fontSize: 12, color: "#5f6368", overflowWrap: "anywhere" }}>Selected: {selected[0]}</div> : <p>Select a node.</p>}
        {selected[0] && !selected[0].startsWith("runtime:") && <button onClick={() => runVerify(selected[0])}>Verify Integrity</button>}
        {selected[0] && verification[selected[0]] && <pre style={{ whiteSpace: "pre-wrap", fontSize: 11 }}>{JSON.stringify(verification[selected[0]], null, 2)}</pre>}
        <h4>Trace</h4>
        {trace ? <pre style={{ whiteSpace: "pre-wrap", fontSize: 11 }}>{JSON.stringify(trace, null, 2)}</pre> : <p style={{ color: "#5f6368" }}>Double-click a persisted node or press Trace.</p>}
      </aside>
    </div>
  );
}
