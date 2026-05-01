import { useEffect, useMemo, useState } from "react";
import { createNumber, createMarkdown, listRuntimes, runRuntime, traceObject, verifyObject } from "./lib/uar";

// (rest unchanged until UI section)

// ADD this state near top:
// const [markdownInput, setMarkdownInput] = useState("");

// ADD this handler inside App():
async function onAddMarkdown() {
  if (!markdownInput.trim()) return;
  const obj = await createMarkdown(markdownInput);
  setNodes((current) => [
    ...current,
    {
      ...obj,
      x: 120 + current.length * 30,
      y: 160 + current.length * 26,
    },
  ]);
  setMarkdownInput("");
}

// In sidebar UI, ADD BELOW number input:
/*
<div style={{ marginTop: 12 }}>
  <textarea
    value={markdownInput}
    placeholder="Paste markdown..."
    onChange={(e) => setMarkdownInput(e.target.value)}
    style={{ width: "100%", height: 80 }}
  />
  <button onClick={onAddMarkdown} style={{ marginTop: 6 }}>
    Add Markdown
  </button>
</div>
*/

export default function App() {
  const [input, setInput] = useState("");
  const [markdownInput, setMarkdownInput] = useState("");
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [runtimes, setRuntimes] = useState<string[]>([]);
  const [activeRuntime, setActiveRuntime] = useState<string | null>(null);
  const [trace, setTrace] = useState<any>(null);
  const [verification, setVerification] = useState<Record<string, any>>({});

  useEffect(() => {
    listRuntimes().then((r) => {
      const names = (r?.runtimes ?? []).map((x: any) => x.name);
      setRuntimes(names);
      setActiveRuntime(names[0] ?? null);
    });
  }, []);

  async function onAdd() {
    if (!input.trim()) return;
    const obj = await createNumber(Number(input));
    setNodes((c) => [...c, { ...obj, x: 80 + c.length * 28, y: 120 + c.length * 24 }]);
    setInput("");
  }

  async function onAddMarkdown() {
    if (!markdownInput.trim()) return;
    const obj = await createMarkdown(markdownInput);
    setNodes((c) => [...c, { ...obj, x: 120 + c.length * 30, y: 160 + c.length * 26 }]);
    setMarkdownInput("");
  }

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <aside style={{ width: 220, padding: 14 }}>
        <h3>UAR</h3>
        <input value={input} onChange={(e) => setInput(e.target.value)} />
        <button onClick={onAdd}>Add</button>

        <div style={{ marginTop: 12 }}>
          <textarea
            value={markdownInput}
            placeholder="Paste markdown..."
            onChange={(e) => setMarkdownInput(e.target.value)}
            style={{ width: "100%", height: 80 }}
          />
          <button onClick={onAddMarkdown} style={{ marginTop: 6 }}>
            Add Markdown
          </button>
        </div>
      </aside>
    </div>
  );
}
