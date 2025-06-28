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
// TIMELINE COMPONENT
// ============================================================================

interface TimelineProps {
  stamps: Array<{
    step: number;
    time: number;
    identifier: string;
  }>;
  currentStep: number;
  isPlaying: boolean;
  onStepChange: (step: number) => void;
  onPlayPause: () => void;
}

const Timeline: React.FC<TimelineProps> = ({
  stamps,
  currentStep,
  isPlaying,
  onStepChange,
  onPlayPause,
}) => {
  const maxStep =
    stamps.length > 0 ? Math.max(...stamps.map((s) => s.step)) : 0;
  const minStep =
    stamps.length > 0 ? Math.min(...stamps.map((s) => s.step)) : 0;
  const totalSteps = maxStep - minStep + 1;

  return (
    <div
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        height: '60px',
        backgroundColor: 'white',
        borderTop: '1px solid #e5e7eb',
        display: 'flex',
        alignItems: 'center',
        padding: '0 16px',
        gap: '12px',
        zIndex: 10,
      }}
    >
      {/* Play/Pause Button */}
      <button
        onClick={onPlayPause}
        style={{
          width: '32px',
          height: '32px',
          borderRadius: '50%',
          border: '1px solid #d1d5db',
          backgroundColor: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = '#f3f4f6';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'white';
        }}
      >
        {isPlaying ? (
          <div style={{ display: 'flex', gap: '2px' }}>
            <div
              style={{
                width: '3px',
                height: '12px',
                backgroundColor: '#374151',
              }}
            />
            <div
              style={{
                width: '3px',
                height: '12px',
                backgroundColor: '#374151',
              }}
            />
          </div>
        ) : (
          <div
            style={{
              width: 0,
              height: 0,
              borderLeft: '8px solid #374151',
              borderTop: '6px solid transparent',
              borderBottom: '6px solid transparent',
              marginLeft: '2px',
            }}
          />
        )}
      </button>

      {/* Timeline Steps */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '0 8px',
        }}
      >
        {Array.from({ length: totalSteps }, (_, index) => {
          const step = minStep + index;
          const isActive = step === currentStep;
          const hasStep = stamps.some((s) => s.step === step);

          return (
            <button
              key={step}
              onClick={() => onStepChange(step)}
              style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                border: isActive ? '2px solid #6366f1' : '1px solid #d1d5db',
                backgroundColor: isActive
                  ? '#6366f1'
                  : hasStep
                  ? '#e5e7eb'
                  : 'white',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                position: 'relative',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = hasStep
                    ? '#d1d5db'
                    : '#f3f4f6';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = hasStep
                    ? '#e5e7eb'
                    : 'white';
                }
              }}
              title={`Step ${step}${
                hasStep
                  ? ` - ${
                      stamps.find((s) => s.step === step)?.identifier || ''
                    }`
                  : ' - No activity'
              }`}
            />
          );
        })}
      </div>

      {/* Step Counter */}
      <div
        style={{
          fontSize: '12px',
          color: '#6b7280',
          minWidth: '60px',
          textAlign: 'right',
        }}
      >
        {currentStep} / {maxStep}
      </div>
    </div>
  );
};

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

  // Timeline state
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const playIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Get max step from stamps
  const maxStep = useMemo(() => {
    return flowData.stamps.length > 0
      ? Math.max(...flowData.stamps.map((s) => s.step))
      : 0;
  }, [flowData.stamps]);

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
      }, 1000); // 1 second per step
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

  // Initialize current step to first step
  useEffect(() => {
    if (flowData.stamps.length > 0) {
      setCurrentStep(Math.min(...flowData.stamps.map((s) => s.step)));
    }
  }, [flowData.stamps]);

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

  // Get nodes and edges for current step
  const getNodesForStep = useCallback(
    (step: number) => {
      return flowData.nodes.filter((node) => node.stamp.step <= step);
    },
    [flowData.nodes],
  );

  const getEdgesForStep = useCallback(
    (step: number) => {
      return flowData.edges.filter((edge) => edge.stamp.step <= step);
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
          opacity: isActive ? 1 : 0.6,
          filter: isActive
            ? 'drop-shadow(0 4px 8px rgba(99, 102, 241, 0.3))'
            : 'none',
        },
      };
    });
  }, [flowData.nodes, positions, currentStep, getNodesForStep]);

  const edges: Edge[] = useMemo(() => {
    const stepEdges = getEdgesForStep(currentStep);
    return stepEdges
      .filter((edge) => edge.source && edge.target)
      .map((edge) => {
        const isActive = edge.stamp.step === currentStep;
        return {
          id: edge.identifier,
          source: edge.source!,
          target: edge.target,
          animated: isActive,
          style: {
            stroke: isActive ? '#6366f1' : '#9ca3af',
            strokeWidth: isActive ? 3 : 2,
            opacity: isActive ? 1 : 0.6,
          },
          label: edge.details?.output
            ? truncateText(String(edge.details.output), 50)
            : undefined,
        };
      });
  }, [flowData.edges, currentStep, getEdgesForStep]);

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
        nodes={nodesState}
        edges={edgesState}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.1 }}
        attributionPosition="bottom-left"
        style={{
          width: '100%',
          height: 'calc(100% - 60px)', // Account for timeline height
        }}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
      >
        <Controls />
        <Background color="#f3f4f6" gap={16} />
      </ReactFlow>

      {/* Timeline */}
      <Timeline
        stamps={flowData.stamps}
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
