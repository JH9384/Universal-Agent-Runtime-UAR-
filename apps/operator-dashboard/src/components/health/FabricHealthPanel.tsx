import React from 'react';

export default function FabricHealthPanel(): JSX.Element {
  return (
    <div style={{ border: '1px solid #444', padding: 16 }}>
      <h3>Fabric Health</h3>
      <ul>
        <li>Continuity Score</li>
        <li>Replay Gaps</li>
        <li>Repair Backlog</li>
        <li>Anomaly Pressure</li>
      </ul>
    </div>
  );
}
