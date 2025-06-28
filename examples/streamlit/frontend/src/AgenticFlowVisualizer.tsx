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
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Edge as RCEdge } from './blocks/Edge';
import { Node as RCNode } from './blocks/Node';

// ============================================================================
// TYPE DEFINITIONS
// ============================================================================

interface DataJsonNode {
  identifier: string;
  node_type: string;
  stamp: {
    step: number;
    time: number;
    identifier: string;
  };
  details: {
    internals?: {
      llm_details?: Array<{
        model_name: string;
        model_provider: string;
        input: Array<{
          role: string;
          content: any;
        }>;
        output: {
          role: string;
          content: any;
        };
        input_tokens: number;
        output_tokens: number;
        total_cost: number;
        system_fingerprint: string;
      }>;
      latency?: {
        total_time: number;
      };
    };
  };
  parent: DataJsonNode | null;
}

interface DataJsonEdge {
  identifier: string;
  source: string | null;
  target: string;
  stamp: {
    step: number;
    time: number;
    identifier: string;
  };
  details: {
    input_args?: any[];
    input_kwargs?: any;
    output?: any;
  };
  parent: DataJsonEdge | null;
}

interface DataJsonStructure {
  nodes: DataJsonNode[];
  edges: DataJsonEdge[];
  stamps: Array<{
    step: number;
    time: number;
    identifier: string;
  }>;
}

interface AgenticFlowVisualizerProps {
  flowData: DataJsonStructure;
  width?: string | number;
  height?: string | number;
  className?: string;
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

  if (node.details?.internals?.llm_details) {
    const llmDetails = node.details.internals.llm_details;
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

const nodeTypes: NodeTypes = {
  agent: RCNode,
};

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
          step: node.stamp?.step,
          time: node.stamp?.time,
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
