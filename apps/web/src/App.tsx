// minimal diff: inject verification
import { useEffect, useMemo, useState } from "react";
import { createNumber, listRuntimes, runRuntime, traceObject, verifyObject } from "./lib/uar";

// rest unchanged until render area

// ADD state
const [verification, setVerification] = useState<Record<string, any>>({});

async function runVerify(id: string) {
  const res = await verifyObject(id);
  setVerification((v) => ({ ...v, [id]: res }));
}

// inside node render add:
<div style={{ display: "flex", gap: 6, marginTop: 4 }}>
  <span style={{ fontSize: 10, color: verification[n.id]?.valid ? "green" : "#aaa" }}>
    {verification[n.id]?.valid ? "✔ hash" : "○ hash"}
  </span>
  <span style={{ fontSize: 10, color: "#ccc" }}>○ replay</span>
  <span style={{ fontSize: 10, color: "#ccc" }}>○ proof</span>
</div>

// inside inspector add button
<button onClick={() => runVerify(selected[0])}>Verify Integrity</button>
