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
  EdgeTypes,
  Connection,
  addEdge,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Edge as RCEdge } from './blocks/Edge';
import { Node as RCNode } from './blocks/Node';
import { Timeline } from './Timeline';

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
  edges?: DataJsonEdge[];
  stamps?: Array<{
    step: number;
    time: number;
    identifier: string;
  }>;
  steps?: Array<{
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
 * Calculates a clean tree layout: parents centered to the left of children, siblings spaced evenly, no overlap.
 */
const calculateAutoLayout = (nodes: DataJsonNode[], edges: DataJsonEdge[]) => {
  // Build maps for fast lookup
  const nodeMap = new Map(nodes.map((n) => [n.identifier, n]));
  const childrenMap = new Map<string, string[]>();
  const parentMap = new Map<string, string>();
  nodes.forEach((n) => childrenMap.set(n.identifier, []));

  // Handle edges if they exist
  if (edges.length > 0) {
    edges.forEach((e) => {
      if (e.source && e.target) {
        childrenMap.get(e.source)?.push(e.target);
        parentMap.set(e.target, e.source);
      }
    });
  } else {
    // If no edges, try to infer relationships from parent field
    nodes.forEach((node) => {
      if (node.parent && node.parent.identifier !== node.identifier) {
        childrenMap.get(node.parent.identifier)?.push(node.identifier);
        parentMap.set(node.identifier, node.parent.identifier);
      }
    });
  }

  // Find root nodes (no parent)
  const roots = nodes.filter((n) => !parentMap.has(n.identifier));

  // Assign levels (depths) - now horizontal levels from left to right
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

  // Calculate subtree heights for each node (for centering vertically)
  const subtreeHeight = new Map<string, number>();
  const nodeHeight = 120; // Approximate node height
  const nodeSpacing = 60;
  const calcSubtreeHeight = (nodeId: string): number => {
    const children = childrenMap.get(nodeId) || [];
    if (children.length === 0) {
      subtreeHeight.set(nodeId, nodeHeight);
      return nodeHeight;
    }
    let height = 0;
    for (const childId of children) {
      height += calcSubtreeHeight(childId);
    }
    height += (children.length - 1) * nodeSpacing;
    subtreeHeight.set(nodeId, height);
    return height;
  };
  roots.forEach((root) => calcSubtreeHeight(root.identifier));

  // Assign positions recursively - now left to right
  const positions = new Map<string, { x: number; y: number }>();
  const levelSpacing = 280; // Horizontal spacing between levels
  const horizontalMargin = 120; // Add margin to the left
  const assignPositions = (nodeId: string, yTop: number, level: number) => {
    const height = subtreeHeight.get(nodeId) || nodeHeight;
    const x = level * levelSpacing + horizontalMargin; // Add margin here
    const children = childrenMap.get(nodeId) || [];
    let y = yTop;
    if (children.length === 0) {
      // Leaf node: center in its height
      positions.set(nodeId, { x, y: yTop + height / 2 - nodeHeight / 2 });
    } else {
      // Internal node: center to the left of its children
      let childY = yTop;
      for (const childId of children) {
        const childHeight = subtreeHeight.get(childId) || nodeHeight;
        assignPositions(childId, childY, level + 1);
        childY += childHeight + nodeSpacing;
      }
      // Center parent to the left of children
      const firstChild = children[0];
      const lastChild = children[children.length - 1];
      const firstPos = positions.get(firstChild)!;
      const lastPos = positions.get(lastChild)!;
      const parentY = (firstPos.y + lastPos.y) / 2;
      positions.set(nodeId, { x, y: parentY });
    }
  };
  // Lay out each tree
  let yCursor = 0;
  for (const root of roots) {
    assignPositions(root.identifier, yCursor, 0);
    yCursor +=
      (subtreeHeight.get(root.identifier) || nodeHeight) + nodeSpacing * 2;
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

const edgeTypes: EdgeTypes = {
  default: RCEdge,
};

const AgenticFlowVisualizer: React.FC<AgenticFlowVisualizerProps> = ({
  flowData,
  width = '100%',
  height = '1000px',
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [containerDimensions, setContainerDimensions] = useState({
    width: typeof width === 'number' ? width : 800,
    height: typeof height === 'number' ? height : 600,
  });

  // Timeline state
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const playIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Get max step from stamps or steps
  const maxStep = useMemo(() => {
    const stamps = flowData.stamps || flowData.steps || [];
    return stamps.length > 0 ? Math.max(...stamps.map((s) => s.step)) : 0;
  }, [flowData.stamps, flowData.steps]);

  // Auto-play functionality
  useEffect(() => {
    if (isPlaying) {
      playIntervalRef.current = setInterval(() => {
        setCurrentStep((prev) => {
          if (prev >= maxStep) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 250); // 1 second per step
    } else {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current);
        playIntervalRef.current = null;
      }
    }

    return () => {
      if (playIntervalRef.current) {
        clearInterval(playIntervalRef.current);
      }
    };
  }, [isPlaying, maxStep]);

  // Initialize current step to last step
  useEffect(() => {
    const stamps = flowData.stamps || flowData.steps || [];
    if (stamps.length > 0) {
      setCurrentStep(Math.max(...stamps.map((s) => s.step)));
    }
  }, [flowData.stamps, flowData.steps]);

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
    return calculateAutoLayout(flowData.nodes, flowData.edges || []);
  }, [flowData.nodes, flowData.edges]);

  // Get nodes and edges for current step
  const getNodesForStep = useCallback(
    (step: number) => {
      return flowData.nodes.filter((node) => node.stamp.step <= step);
    },
    [flowData.nodes],
  );

  const getEdgesForStep = useCallback(
    (step: number) => {
      return (flowData.edges || []).filter((edge) => edge.stamp.step <= step);
    },
    [flowData.edges],
  );

  // Convert flow data to ReactFlow format with step filtering
  const nodes: Node[] = useMemo(() => {
    const stepNodes = getNodesForStep(currentStep);
    return stepNodes.map((node) => {
      const position = positions.get(node.identifier) || { x: 0, y: 0 };
      const { description } = extractLLMDetails(node);
      const isActive = node.stamp.step === currentStep;

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
          isActive,
        },
        style: {
          filter: isActive
            ? 'drop-shadow(0 4px 8px rgba(99, 102, 241, 0.3))'
            : 'none',
        },
      };
    });
  }, [positions, currentStep, getNodesForStep]);

  const edges: Edge[] = useMemo(() => {
    const stepEdges = getEdgesForStep(currentStep);
    return stepEdges
      .filter((edge) => edge.source && edge.target)
      .map((edge) => {
        const isActive = edge.stamp.step === currentStep;
        return {
          id: edge.identifier,
          type: 'default',
          source: edge.source!,
          target: edge.target,
          animated: isActive,
          bidirectional: true, // Enable bidirectional edges with arrow heads
          style: {
            stroke: isActive ? '#6366f1' : '#9ca3af',
            strokeWidth: isActive ? 3 : 2,
          },
          label: edge.stamp?.identifier
            ? truncateText(String(edge.stamp.identifier), 50)
            : undefined,
          data: {
            label: edge.stamp?.identifier
              ? truncateText(String(edge.stamp.identifier), 50)
              : undefined,
            source: edge.source!,
            target: edge.target,
            step: edge.stamp?.step,
            time: edge.stamp?.time,
            details: edge.details,
          },
        };
      });
  }, [currentStep, getEdgesForStep]);

  const [nodesState, setNodes, onNodesChange] = useNodesState(nodes);
  const [edgesState, setEdges, onEdgesChange] = useEdgesState(edges);

  // Update nodes and edges when currentStep changes
  useEffect(() => {
    setNodes(nodes);
  }, [nodes, setNodes]);

  useEffect(() => {
    setEdges(edges);
  }, [edges, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds: Edge[]) => addEdge(params, eds)),
    [setEdges],
  );

  const handleStepChange = useCallback((step: number) => {
    setCurrentStep(step);
    setIsPlaying(false);
  }, []);

  const handlePlayPause = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  // Function to convert client (screen) coordinates to SVG coordinates
  const clientToSvgCoords = (clientX: number, clientY: number) => {
    if (!svgRef.current) return { x: 0, y: 0 };
    const pt = svgRef.current.createSVGPoint();
    pt.x = clientX;
    pt.y = clientY;
    const svgP = pt.matrixTransform(svgRef.current.getScreenCTM()?.inverse());
    return { x: svgP.x, y: svgP.y };
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
        minWidth: '800px',
        minHeight: '600px',
      }}
      className={className}
    >
      <ReactFlow
        nodes={nodesState}
        edges={edgesState}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        edgeTypes={{
          default: (edgeProps) => (
            <RCEdge
              {...edgeProps}
              clientToSvgCoords={clientToSvgCoords}
              svgRef={svgRef}
            />
          ),
        }}
        fitView
        fitViewOptions={{ padding: 0.1 }}
        attributionPosition="bottom-left"
        style={{
          width: '100%',
          height: 'calc(100% - 60px)', // Account for timeline height
        }}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
        onInit={() => {
          if (containerRef.current) {
            const svg = containerRef.current.querySelector('svg');
            if (svg) svgRef.current = svg as SVGSVGElement;
          }
        }}
      >
        <Controls />
        <Background color="#f3f4f6" gap={16} />
      </ReactFlow>

      {/* Timeline */}
      <Timeline
        stamps={flowData.stamps || flowData.steps || []}
        currentStep={currentStep}
        isPlaying={isPlaying}
        onStepChange={handleStepChange}
        onPlayPause={handlePlayPause}
      />

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
