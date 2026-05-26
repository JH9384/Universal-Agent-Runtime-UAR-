import React from 'react';

import FabricHealthPanel from '../components/health/FabricHealthPanel';
import ControlSurface from '../components/controls/ControlSurface';
import AnomalyOverlay from '../components/anomaly/AnomalyOverlay';

export default function FabricOverview(): JSX.Element {
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <FabricHealthPanel />
      <AnomalyOverlay />
      <ControlSurface />
    </div>
  );
}
