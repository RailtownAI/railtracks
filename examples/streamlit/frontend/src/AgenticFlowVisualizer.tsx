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
  Handle,
  Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

// Custom Agent Node Component
const AgentNode: React.FC<{
  data: {
    label: string;
    description: string;
    nodeType: string;
    step?: number;
    time?: number;
  };
}> = ({ data }) => {
  return (
    <div className="agent-node">
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: '#6366f1' }}
      />
      <div className="agent-header">
        <div className="agent-icon">🤖</div>
        <div className="agent-label">{data.label}</div>
      </div>
      <div className="agent-description">{data.description}</div>
      {data.step && (
        <div className="agent-meta">
          <span className="step">Step: {data.step}</span>
          {data.time && (
            <span className="time">
              {new Date(data.time * 1000).toLocaleTimeString()}
            </span>
          )}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: '#6366f1' }}
      />
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

// Auto-layout utility function
const calculateAutoLayout = (nodes: any[], edges: any[]) => {
  const nodeMap = new Map();
  const childrenMap = new Map();
  const levelMap = new Map();

  // Initialize maps
  nodes.forEach((node) => {
    nodeMap.set(node.identifier, node);
    childrenMap.set(node.identifier, []);
    levelMap.set(node.identifier, 0);
  });

  // Build parent-child relationships
  edges.forEach((edge) => {
    if (edge.source && edge.target) {
      const children = childrenMap.get(edge.source) || [];
      children.push(edge.target);
      childrenMap.set(edge.source, children);
    }
  });

  // Calculate levels (BFS)
  const visited = new Set();
  const queue: Array<{ nodeId: string; level: number }> = [];

  // Find root nodes (nodes with no incoming edges)
  const hasIncoming = new Set();
  edges.forEach((edge) => {
    if (edge.target) {
      hasIncoming.add(edge.target);
    }
  });

  nodes.forEach((node) => {
    if (!hasIncoming.has(node.identifier)) {
      queue.push({ nodeId: node.identifier, level: 0 });
    }
  });

  while (queue.length > 0) {
    const { nodeId, level } = queue.shift()!;
    if (visited.has(nodeId)) continue;

    visited.add(nodeId);
    levelMap.set(nodeId, level);

    const children = childrenMap.get(nodeId) || [];
    children.forEach((childId: string) => {
      if (!visited.has(childId)) {
        queue.push({ nodeId: childId, level: level + 1 });
      }
    });
  }

  // Group nodes by level
  const levelGroups = new Map();
  nodes.forEach((node) => {
    const level = levelMap.get(node.identifier) || 0;
    if (!levelGroups.has(level)) {
      levelGroups.set(level, []);
    }
    levelGroups.get(level).push(node.identifier);
  });

  // Calculate positions
  const positions = new Map();
  const nodeWidth = 250;
  const nodeHeight = 120;
  const levelSpacing = 300;
  const nodeSpacing = 50;

  levelGroups.forEach((nodeIds: string[], level: number) => {
    const levelWidth = nodeIds.length * (nodeWidth + nodeSpacing) - nodeSpacing;
    const startX = -levelWidth / 2;

    nodeIds.forEach((nodeId: string, index: number) => {
      const x = startX + index * (nodeWidth + nodeSpacing);
      const y = level * levelSpacing;
      positions.set(nodeId, { x, y });
    });
  });

  return positions;
};

// Type definitions for data.json structure
interface DataJsonNode {
  identifier: string;
  node_type: string;
  details: {
    stamp: {
      time: number;
      step: number;
      identifier: string;
    };
    details: any;
  };
}

interface DataJsonEdge {
  identifier: string;
  source: string | null;
  target: string;
  details: {
    stamp: {
      time: number;
      step: number;
      identifier: string;
    };
    input: any;
    output: any;
  };
}

interface DataJsonStructure {
  nodes: DataJsonNode[];
  edges: DataJsonEdge[];
}

interface AgenticFlowVisualizerProps {
  flowData: DataJsonStructure;
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
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [containerDimensions, setContainerDimensions] = React.useState({
    width: typeof width === 'number' ? width : 800,
    height: typeof height === 'number' ? height : 600,
  });

  // Update dimensions when width/height props change
  React.useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setContainerDimensions({
          width: rect.width || (typeof width === 'number' ? width : 800),
          height: rect.height || (typeof height === 'number' ? height : 600),
        });
      }
    };

    updateDimensions();

    // Use ResizeObserver if available, otherwise fallback to window resize
    if (window.ResizeObserver && containerRef.current) {
      const resizeObserver = new ResizeObserver(updateDimensions);
      resizeObserver.observe(containerRef.current);
      return () => resizeObserver.disconnect();
    } else {
      window.addEventListener('resize', updateDimensions);
      return () => window.removeEventListener('resize', updateDimensions);
    }
  }, [width, height]);

  // Calculate auto-layout positions
  const positions = React.useMemo(() => {
    return calculateAutoLayout(flowData.nodes, flowData.edges);
  }, [flowData.nodes, flowData.edges]);

  // Convert flow data to ReactFlow format
  const initialNodes: Node[] = React.useMemo(() => {
    return flowData.nodes.map((node) => {
      const position = positions.get(node.identifier) || { x: 0, y: 0 };

      // Extract LLM details if available
      let description = node.node_type;
      let modelInfo = '';

      if (node.details?.details?.llm_details) {
        const llmDetails = node.details.details.llm_details;
        if (llmDetails.length > 0) {
          const lastLLM = llmDetails[llmDetails.length - 1];
          modelInfo = `${lastLLM.model_name} (${lastLLM.model_provider})`;
          description = `${node.node_type}\n${modelInfo}`;
        }
      }

      return {
        id: node.identifier,
        type: 'agent',
        position,
        data: {
          label: node.node_type,
          description,
          nodeType: node.node_type,
          step: node.details?.stamp?.step,
          time: node.details?.stamp?.time,
        },
      };
    });
  }, [flowData.nodes, positions]);

  const initialEdges: Edge[] = React.useMemo(() => {
    return flowData.edges
      .filter((edge) => edge.source && edge.target) // Filter out edges with null source
      .map((edge) => ({
        id: edge.identifier,
        source: edge.source!,
        target: edge.target,
        animated: true,
        style: {
          stroke: '#6366f1',
          strokeWidth: 2,
        },
        label: edge.details?.output
          ? String(edge.details.output).substring(0, 50) +
            (String(edge.details.output).length > 50 ? '...' : '')
          : undefined,
      }));
  }, [flowData.edges]);

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
      ref={containerRef}
      style={{
        width: typeof width === 'number' ? `${width}px` : width,
        height: typeof height === 'number' ? `${height}px` : height,
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        overflow: 'hidden',
        position: 'relative',
        minWidth: '400px',
        minHeight: '300px',
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
        fitViewOptions={{ padding: 0.1 }}
        attributionPosition="bottom-left"
        style={{
          width: '100%',
          height: '100%',
        }}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
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
            max-width: 250px;
            transition: all 0.2s ease;
            position: relative;
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
            word-break: break-word;
          }
          
          .agent-description {
            color: #6b7280;
            font-size: 12px;
            line-height: 1.4;
            word-break: break-word;
            white-space: pre-line;
          }
          
          .agent-meta {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #e5e7eb;
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: #9ca3af;
          }
          
          .step {
            background: #f3f4f6;
            padding: 2px 6px;
            border-radius: 4px;
          }
          
          .time {
            font-family: monospace;
          }
          
          .react-flow__handle {
            width: 8px;
            height: 8px;
            border: 2px solid #6366f1;
          }
          
          .react-flow__edge-label {
            font-size: 10px;
            background: white;
            padding: 2px 4px;
            border-radius: 4px;
            border: 1px solid #e5e7eb;
            max-width: 150px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        `}
      </style>
    </div>
  );
};

export default AgenticFlowVisualizer;
