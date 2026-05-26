import React from 'react';

export default function ControlSurface(): JSX.Element {
  return (
    <div style={{ border: '1px solid #666', padding: 16 }}>
      <h3>Runtime Control Surface</h3>

      <button>Pause Replay</button>
      <button>Resume Replay</button>
      <button>Start Restoration</button>
      <button>Escalate Repair</button>
      <button>Throttle Sync</button>
    </div>
  );
}
