import React from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  NodeTypes,
  Connection,
  addEdge,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';

// Custom Agent Node Component
const AgentNode: React.FC<{
  data: {
    label: string;
    description: string;
  };
}> = ({ data }) => {
  return (
    <div className="agent-node">
      <div className="agent-header">
        <div className="agent-icon">🤖</div>
        <div className="agent-label">{data.label}</div>
      </div>
      <div className="agent-description">{data.description}</div>
    </div>
  );
};

// Custom Edge Component
const CustomEdge: React.FC<{
  id: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  sourcePosition: any;
  targetPosition: any;
  style?: React.CSSProperties;
  markerEnd?: string;
}> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
}) => {
  const [edgePath] = React.useMemo(() => {
    const centerX = (sourceX + targetX) / 2;
    const centerY = (sourceY + targetY) / 2;

    const path = `M ${sourceX} ${sourceY} Q ${centerX} ${centerY} ${targetX} ${targetY}`;

    return [path];
  }, [sourceX, sourceY, targetX, targetY]);

  return (
    <g>
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        markerEnd={markerEnd}
        style={style}
      />
    </g>
  );
};

// Type definitions
interface AgenticFlowData {
  nodes: Array<{
    id: string;
    type: string;
    position: { x: number; y: number };
    data: {
      label: string;
      description: string;
    };
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
  }>;
}

interface AgenticFlowVisualizerProps {
  flowData: AgenticFlowData;
  width?: string | number;
  height?: string | number;
  className?: string;
}

// Main Component
const AgenticFlowVisualizer: React.FC<AgenticFlowVisualizerProps> = ({
  flowData,
  width = '100%',
  height = '600px',
  className = '',
}) => {
  // Convert flow data to ReactFlow format
  const initialNodes: Node[] = flowData.nodes.map((node) => ({
    id: node.id,
    type: 'agent',
    position: node.position,
    data: node.data,
  }));

  const initialEdges: Edge[] = flowData.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    animated: true,
    style: {
      stroke: '#6366f1',
      strokeWidth: 2,
    },
  }));

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = React.useCallback(
    (params: Connection) => setEdges((eds: Edge[]) => addEdge(params, eds)),
    [setEdges],
  );

  // Custom node types
  const nodeTypes: NodeTypes = {
    agent: AgentNode,
  };

  return (
    <div
      style={{
        width,
        height,
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        overflow: 'hidden',
      }}
      className={className}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
      >
        <Controls />
        <Background color="#f3f4f6" gap={16} />
      </ReactFlow>

      <style>
        {`
          .agent-node {
            padding: 12px;
            border-radius: 8px;
            background: white;
            border: 2px solid #e5e7eb;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            min-width: 200px;
            transition: all 0.2s ease;
          }
          
          .agent-node:hover {
            border-color: #6366f1;
            box-shadow: 0 4px 8px rgba(99, 102, 241, 0.2);
          }
          
          .agent-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
          }
          
          .agent-icon {
            font-size: 20px;
          }
          
          .agent-label {
            font-weight: 600;
            color: #1f2937;
            font-size: 14px;
          }
          
          .agent-description {
            color: #6b7280;
            font-size: 12px;
            line-height: 1.4;
          }
        `}
      </style>
    </div>
  );
};

export default AgenticFlowVisualizer;
