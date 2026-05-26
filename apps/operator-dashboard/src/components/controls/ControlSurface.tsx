import React from 'react';

import { sendOperatorAction } from '../../runtime/actionClient';

export default function ControlSurface(): JSX.Element {
  return (
    <div style={{ border: '1px solid #666', padding: 16 }}>
      <h3>Runtime Control Surface</h3>

      <button onClick={() => sendOperatorAction('pause-replay')}>
        Pause Replay
      </button>

      <button onClick={() => sendOperatorAction('resume-replay')}>
        Resume Replay
      </button>

      <button onClick={() => sendOperatorAction('start-restoration')}>
        Start Restoration
      </button>

      <button onClick={() => sendOperatorAction('escalate-repair')}>
        Escalate Repair
      </button>

      <button onClick={() => sendOperatorAction('throttle-sync')}>
        Throttle Sync
      </button>
    </div>
  );
}
