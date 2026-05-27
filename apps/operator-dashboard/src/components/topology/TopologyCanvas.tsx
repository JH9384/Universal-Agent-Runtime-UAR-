import React, { useMemo } from 'react';
import ReactFlow, { Background, Controls, Edge, MiniMap, Node } from 'reactflow';
import 'reactflow/dist/style.css';

import { useTopologyStore } from '../../store/topologyStore';

export default function TopologyCanvas(): JSX.Element {
  const runtimeNodes = useTopologyStore((state) => state.nodes);
  const runtimeEdges = useTopologyStore((state) => state.edges);

  const nodes: Node[] = useMemo(
    () =>
      runtimeNodes.map((node, index) => ({
        id: node.id,
        position: { x: 160 * index, y: 80 + (index % 2) * 120 },
        data: { label: `${node.id} · ${node.status}` },
        type: 'default',
      })),
    [runtimeNodes],
  );

  const edges: Edge[] = useMemo(
    () =>
      runtimeEdges.map((edge) => ({
        id: `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        animated: edge.animated,
      })),
    [runtimeEdges],
  );

  return (
    <div style={{ border: '1px solid #333', height: 460, minHeight: 460 }}>
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <MiniMap />
        <Controls />
        <Background />
      </ReactFlow>
    </div>
  );
}
