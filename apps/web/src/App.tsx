import { useEffect, useState } from "react";
import { createNumber, listRuntimes, runRuntime, traceObject } from "./lib/uar";

export default function App() {
  const [input, setInput] = useState("");
  const [objects, setObjects] = useState<any[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [runtimes, setRuntimes] = useState<string[]>([]);
  const [activeRuntime, setActiveRuntime] = useState<string | null>(null);
  const [trace, setTrace] = useState<any>(null);

  useEffect(() => {
    listRuntimes().then((r) => {
      const names = (r?.runtimes ?? []).map((x: any) => x.name);
      setRuntimes(names);
      setActiveRuntime(names[0] ?? null);
    }).catch(() => {});
  }, []);

  async function onAdd() {
    const obj = await createNumber(Number(input));
    setObjects((o) => [...o, obj]);
    setInput("");
  }

  async function onRun() {
    if (!activeRuntime) return;
    const res = await runRuntime(activeRuntime, selected);
    const newObj = {
      id: res.output,
      label: "result",
      value: res.result,
      kind: "result",
    };
    setObjects((o) => [...o, newObj]);
    setSelected([res.output]);
  }

  async function onTrace() {
    if (!selected[0]) return;
    const t = await traceObject(selected[0]);
    setTrace(t);
  }

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      {/* Sidebar */}
      <div style={{ width: 200, borderRight: "1px solid #ddd", padding: 10 }}>
        <h4>Objects</h4>
        {objects.map((o) => (
          <div key={o.id} onClick={() => setSelected([o.id])} style={{ padding: 4, cursor: "pointer" }}>
            {o.label}
          </div>
        ))}
      </div>

      {/* Canvas */}
      <div style={{ flex: 1, padding: 20 }}>
        <h3>Canvas</h3>
        <div>
          <input value={input} onChange={(e) => setInput(e.target.value)} />
          <button onClick={onAdd}>Add</button>
        </div>

        <div style={{ marginTop: 20 }}>
          {objects.map((o) => (
            <div key={o.id} style={{ display: "inline-block", padding: 10, border: "1px solid #ccc", margin: 5 }}>
              {o.label}
            </div>
          ))}
        </div>

        <div style={{ marginTop: 20 }}>
          <select value={activeRuntime ?? ""} onChange={(e) => setActiveRuntime(e.target.value)}>
            {runtimes.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
          <button onClick={onRun}>Run</button>
          <button onClick={onTrace}>Trace</button>
        </div>
      </div>

      {/* Inspector */}
      <div style={{ width: 300, borderLeft: "1px solid #ddd", padding: 10 }}>
        <h4>Inspector</h4>
        {selected[0] && <div>Selected: {selected[0]}</div>}
        {trace && <pre>{JSON.stringify(trace, null, 2)}</pre>}
      </div>
    </div>
  );
}
