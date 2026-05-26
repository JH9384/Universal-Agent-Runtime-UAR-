import React from 'react';

import TopologyCanvas from '../components/topology/TopologyCanvas';

export default function TopologyView(): JSX.Element {
  return (
    <div style={{ padding: 16 }}>
      <TopologyCanvas />
    </div>
  );
}
