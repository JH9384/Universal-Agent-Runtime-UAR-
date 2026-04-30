import { useState } from "react";
import { createNumber, add, history } from "./lib/uar";

export default function App() {
  const [input, setInput] = useState("");
  const [items, setItems] = useState<any[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<number | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);
  const [trace, setTrace] = useState<any>(null);

  async function onAdd() {
    const obj = await createNumber(Number(input));
    setItems([...items, obj]);
    setInput("");
  }

  async function onRun() {
    const res = await add(selected);
    setResult(res.result);
    setResultId(res.id);
  }

  async function onHistory() {
    if (!resultId) return;
    const t = await history(resultId);
    setTrace(t);
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Add Numbers</h2>
      <input value={input} onChange={e => setInput(e.target.value)} />
      <button onClick={onAdd}>+</button>

      <div>
        {items.map(it => (
          <button key={it.id} onClick={() => setSelected([...selected, it.id])}>
            {it.value}
          </button>
        ))}
      </div>

      <button onClick={onRun}>Add Selected</button>

      {result && <h3>Result: {result}</h3>}

      <button onClick={onHistory}>View History</button>
      {trace && <pre>{JSON.stringify(trace, null, 2)}</pre>}
    </div>
  );
}
