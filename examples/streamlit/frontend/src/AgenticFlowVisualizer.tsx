import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
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

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

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

interface AgentNodeData {
  label: string;
  description: string;
  nodeType: string;
  step?: number;
  time?: number;
}

interface CustomEdgeProps {
  id: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  sourcePosition: any;
  targetPosition: any;
  style?: React.CSSProperties;
  markerEnd?: string;
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Calculates a clean tree layout: parents centered above children, siblings spaced evenly, no overlap.
 */
const calculateAutoLayout = (nodes: DataJsonNode[], edges: DataJsonEdge[]) => {
  // Build maps for fast lookup
  const nodeMap = new Map(nodes.map((n) => [n.identifier, n]));
  const childrenMap = new Map<string, string[]>();
  const parentMap = new Map<string, string>();
  nodes.forEach((n) => childrenMap.set(n.identifier, []));
  edges.forEach((e) => {
    if (e.source && e.target) {
      childrenMap.get(e.source)?.push(e.target);
      parentMap.set(e.target, e.source);
    }
  });

  // Find root nodes (no parent)
  const roots = nodes.filter((n) => !parentMap.has(n.identifier));

  // Assign levels (depths)
  const levelMap = new Map<string, number>();
  const assignLevels = (nodeId: string, level: number) => {
    levelMap.set(nodeId, level);
    for (const childId of childrenMap.get(nodeId) || []) {
      assignLevels(childId, level + 1);
    }
  };
  roots.forEach((root) => assignLevels(root.identifier, 0));

  // Group nodes by level
  const levels: string[][] = [];
  nodes.forEach((n) => {
    const lvl = levelMap.get(n.identifier) ?? 0;
    if (!levels[lvl]) levels[lvl] = [];
    levels[lvl].push(n.identifier);
  });

  // Calculate subtree widths for each node (for centering)
  const subtreeWidth = new Map<string, number>();
  const nodeWidth = 280;
  const nodeSpacing = 60;
  const calcSubtreeWidth = (nodeId: string): number => {
    const children = childrenMap.get(nodeId) || [];
    if (children.length === 0) {
      subtreeWidth.set(nodeId, nodeWidth);
      return nodeWidth;
    }
    let width = 0;
    for (const childId of children) {
      width += calcSubtreeWidth(childId);
    }
    width += (children.length - 1) * nodeSpacing;
    subtreeWidth.set(nodeId, width);
    return width;
  };
  roots.forEach((root) => calcSubtreeWidth(root.identifier));

  // Assign positions recursively
  const positions = new Map<string, { x: number; y: number }>();
  const levelSpacing = 180;
  const assignPositions = (nodeId: string, xLeft: number, level: number) => {
    const width = subtreeWidth.get(nodeId) || nodeWidth;
    const y = level * levelSpacing;
    const children = childrenMap.get(nodeId) || [];
    let x = xLeft;
    if (children.length === 0) {
      // Leaf node: center in its width
      positions.set(nodeId, { x: xLeft + width / 2 - nodeWidth / 2, y });
    } else {
      // Internal node: center above its children
      let childX = xLeft;
      for (const childId of children) {
        const childWidth = subtreeWidth.get(childId) || nodeWidth;
        assignPositions(childId, childX, level + 1);
        childX += childWidth + nodeSpacing;
      }
      // Center parent above children
      const firstChild = children[0];
      const lastChild = children[children.length - 1];
      const firstPos = positions.get(firstChild)!;
      const lastPos = positions.get(lastChild)!;
      const parentX = (firstPos.x + lastPos.x) / 2;
      positions.set(nodeId, { x: parentX, y });
    }
  };
  // Lay out each tree
  let xCursor = 0;
  for (const root of roots) {
    assignPositions(root.identifier, xCursor, 0);
    xCursor +=
      (subtreeWidth.get(root.identifier) || nodeWidth) + nodeSpacing * 2;
  }

  return positions;
};

/**
 * Extracts LLM details from node data for display
 */
const extractLLMDetails = (
  node: DataJsonNode,
): { description: string; modelInfo: string } => {
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

  return { description, modelInfo };
};

/**
 * Truncates text to specified length with ellipsis
 */
const truncateText = (text: string, maxLength: number): string => {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
};

// ============================================================================
// CUSTOM COMPONENTS
// ============================================================================

/**
 * Custom node component for displaying agent information
 */
const AgentNode: React.FC<{ data: AgentNodeData }> = ({ data }) => {
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

/**
 * Custom edge component with curved paths
 */
const CustomEdge: React.FC<CustomEdgeProps> = ({
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
  const [edgePath] = useMemo(() => {
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

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const nodeTypes: NodeTypes = {
  agent: AgentNode,
};

/**
 * Main component for visualizing agentic flow data
 */
const AgenticFlowVisualizer: React.FC<AgenticFlowVisualizerProps> = ({
  flowData,
  width = '100%',
  height = '600px',
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerDimensions, setContainerDimensions] = useState({
    width: typeof width === 'number' ? width : 800,
    height: typeof height === 'number' ? height : 600,
  });

  // Update dimensions when width/height props change
  useEffect(() => {
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
  const positions = useMemo(() => {
    return calculateAutoLayout(flowData.nodes, flowData.edges);
  }, [flowData.nodes, flowData.edges]);

  // Convert flow data to ReactFlow format
  const initialNodes: Node[] = useMemo(() => {
    return flowData.nodes.map((node) => {
      const position = positions.get(node.identifier) || { x: 0, y: 0 };
      const { description } = extractLLMDetails(node);

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

  const initialEdges: Edge[] = useMemo(() => {
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
          ? truncateText(String(edge.details.output), 50)
          : undefined,
      }));
  }, [flowData.edges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds: Edge[]) => addEdge(params, eds)),
    [setEdges],
  );

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
