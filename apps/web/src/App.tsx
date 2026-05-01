import { useEffect, useMemo, useState } from "react";
import { createNumber, listRuntimes, runRuntime, traceObject } from "./lib/uar";

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
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [runtimes, setRuntimes] = useState<string[]>([]);
  const [activeRuntime, setActiveRuntime] = useState<string | null>(null);
  const [trace, setTrace] = useState<any>(null);
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

  async function onRun() {
    if (!activeRuntime || selected.length === 0) return;
    const runInputs = [...selected];
    const res = await runRuntime(activeRuntime, runInputs);
    const centerX = selectedNodes.length ? selectedNodes.reduce((s, n) => s + n.x, 0) / selectedNodes.length : 200;
    const maxY = selectedNodes.length ? Math.max(...selectedNodes.map((n) => n.y)) : 120;
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
    if (!selected[0]) return;
    const t = await traceObject(selected[0]);
    setTrace(t);
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

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "Inter, system-ui, sans-serif", color: "#202124" }} onMouseMove={onMouseMove} onMouseUp={() => setDragging(null)}>
      <aside style={{ width: 220, borderRight: "1px solid #e0e0e0", padding: 14, background: "#fafafa" }}>
        <h3 style={{ marginTop: 0 }}>UAR</h3>
        <div style={{ display: "flex", gap: 6 }}>
          <input style={{ flex: 1 }} value={input} placeholder="number" onChange={(e) => setInput(e.target.value)} />
          <button onClick={onAdd}>Add</button>
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
            onDoubleClick={() => traceObject(n.id).then(setTrace)}
            style={{
              position: "absolute",
              left: n.x,
              top: n.y,
              width: 140,
              padding: 12,
              borderRadius: 14,
              background: n.kind === "result" ? "#eef2ff" : "#fff",
              border: selected.includes(n.id) ? "2px solid #1a73e8" : "1px solid #dadce0",
              boxShadow: "0 6px 18px rgba(60,64,67,0.12)",
              cursor: "grab",
              userSelect: "none",
            }}
          >
            <strong>{n.label}</strong>
            <div style={{ fontSize: 12, color: "#5f6368" }}>{n.kind}</div>
            <div style={{ fontSize: 10, color: "#80868b" }}>{shortId(n.id)}</div>
          </div>
        ))}

        {floatingPosition && (
          <div style={{ position: "absolute", left: floatingPosition.x, top: floatingPosition.y, transform: "translateX(-20%)", display: "flex", gap: 8, alignItems: "center", padding: "8px 10px", borderRadius: 999, background: "#fff", border: "1px solid #dadce0", boxShadow: "0 8px 24px rgba(60,64,67,0.18)" }}>
            <select value={activeRuntime ?? ""} onChange={(e) => setActiveRuntime(e.target.value)}>
              {runtimes.map((r) => <option key={r}>{r}</option>)}
            </select>
            <button onClick={onRun}>Run</button>
            <button onClick={onTrace}>Trace</button>
          </div>
        )}
      </main>

      <aside style={{ width: 320, borderLeft: "1px solid #e0e0e0", padding: 14, background: "#fff" }}>
        <h4>Inspector</h4>
        {selected[0] ? <div style={{ fontSize: 12, color: "#5f6368", overflowWrap: "anywhere" }}>Selected: {selected[0]}</div> : <p>Select a node.</p>}
        <h4>Trace</h4>
        {trace ? <pre style={{ whiteSpace: "pre-wrap", fontSize: 11 }}>{JSON.stringify(trace, null, 2)}</pre> : <p style={{ color: "#5f6368" }}>Double-click a node or press Trace.</p>}
      </aside>
    </div>
  );
}
