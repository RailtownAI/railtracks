import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useReactFlow } from 'reactflow';
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
import { PanelLeft, PanelRight } from 'lucide-react';
import { Edge as RCEdge } from './blocks/Edge';
import { Node as RCNode } from './blocks/Node';
import { Timeline } from './Timeline';
import { VerticalTimeline } from './VerticalTimeline';

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
        input_tokens: number | null;
        output_tokens: number | null;
        total_cost: number | null;
        system_fingerprint: string | null;
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
    state?: string;
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
 * Calculates a clean tree layout: parents centered above children, siblings spaced evenly, no overlap.
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

  // Assign levels (depths) - now vertical levels from top to bottom
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

  // Calculate subtree widths for each node (for centering horizontally)
  const subtreeWidth = new Map<string, number>();
  const nodeWidth = 200; // Approximate node width
  const nodeSpacing = 100; // Horizontal spacing between nodes
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

  // Assign positions recursively - now top to bottom
  const positions = new Map<string, { x: number; y: number }>();
  const levelSpacing = 300; // Increased vertical spacing between levels
  const verticalMargin = 100; // Add margin to the top
  const assignPositions = (nodeId: string, xLeft: number, level: number) => {
    const width = subtreeWidth.get(nodeId) || nodeWidth;
    const y = level * levelSpacing + verticalMargin; // Add margin here
    const children = childrenMap.get(nodeId) || [];

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

  // Timeline visibility state
  const [showTimelines, setShowTimelines] = useState(false);

  // Drawer state
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [selectedData, setSelectedData] = useState<{
    type: 'node' | 'edge';
    data: any;
  } | null>(null);

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

  // Initialize current step to last step and pan to hub node
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

  // Handle node inspection
  const handleNodeInspect = useCallback((nodeData: any) => {
    setSelectedData({ type: 'node', data: nodeData });
    setIsDrawerOpen(true);
  }, []);

  // Handle edge inspection
  const handleEdgeInspect = useCallback(
    (edgeData: any) => {
      // Find the edge in the current edges to get the ID
      const currentEdges = getEdgesForStep(currentStep);
      const edge = currentEdges.find(
        (e) => e.source === edgeData.source && e.target === edgeData.target,
      );
      const edgeWithId = {
        ...edgeData,
        id: edge?.identifier || 'N/A',
      };
      setSelectedData({ type: 'edge', data: edgeWithId });
      setIsDrawerOpen(true);
    },
    [getEdgesForStep, currentStep],
  );

  // Convert flow data to ReactFlow format with step filtering
  const nodes: Node[] = useMemo(() => {
    const stepNodes = getNodesForStep(currentStep);
    const stepEdges = getEdgesForStep(currentStep);
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
          onInspect: handleNodeInspect,
          id: node.identifier, // Add id for zoom functionality
          edges: stepEdges, // Pass edges to the node
        },
        style: {
          filter: isActive
            ? 'drop-shadow(0 4px 8px rgba(99, 102, 241, 0.3))'
            : 'none',
        },
      };
    });
  }, [
    positions,
    currentStep,
    getNodesForStep,
    getEdgesForStep,
    handleNodeInspect,
  ]);

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

  const reactFlowInstance = useReactFlow();

  // Pan to hub node (most connected node) on initial load
  useEffect(() => {
    if (nodes.length > 0 && reactFlowInstance) {
      // Find the node with the most connections
      const nodeConnectionCounts = new Map<string, number>();

      // Count incoming and outgoing connections for each node
      edges.forEach((edge) => {
        // Count outgoing connections (source)
        const sourceCount = nodeConnectionCounts.get(edge.source) || 0;
        nodeConnectionCounts.set(edge.source, sourceCount + 1);

        // Count incoming connections (target)
        const targetCount = nodeConnectionCounts.get(edge.target) || 0;
        nodeConnectionCounts.set(edge.target, targetCount + 1);
      });

      // Find the node with the highest connection count
      let hubNodeId = '';
      let maxConnections = 0;

      nodeConnectionCounts.forEach((count, nodeId) => {
        if (count > maxConnections) {
          maxConnections = count;
          hubNodeId = nodeId;
        }
      });

      // If no hub node found (no edges), use the first node
      if (!hubNodeId && nodes.length > 0) {
        hubNodeId = nodes[0].id;
      }

      // Pan to the hub node
      if (hubNodeId) {
        setTimeout(() => {
          reactFlowInstance.fitView({
            nodes: [{ id: hubNodeId }],
            duration: 1000,
            padding: 0.2,
            minZoom: 0.2,
            maxZoom: 0.8,
          });
        }, 500); // Small delay to ensure nodes are rendered
      }
    }
  }, [nodes, edges, reactFlowInstance]);

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
      {/* Collapsible Side Panel */}
      <div className={`side-panel ${showTimelines ? 'expanded' : 'collapsed'}`}>
        {!showTimelines && (
          <button
            className="panel-toggle"
            onClick={() => setShowTimelines(!showTimelines)}
            title="Expand Panel"
          >
            <PanelLeft size={20} />
          </button>
        )}

        {showTimelines && (
          <div className="panel-content">
            <VerticalTimeline
              stamps={flowData.stamps || flowData.steps || []}
              currentStep={currentStep}
              onStepChange={handleStepChange}
              onToggle={() => setShowTimelines(false)}
            />
          </div>
        )}
      </div>

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
              onInspect={handleEdgeInspect}
            />
          ),
        }}
        attributionPosition="bottom-left"
        style={{
          width: showTimelines ? 'calc(100% - 280px)' : '100%', // Account for side panel width when visible
          height: 'calc(100% - 60px)', // Account for timeline height
          marginLeft: showTimelines ? '280px' : '0', // Push content to the right of side panel when visible
        }}
        defaultViewport={{ x: 0, y: 0, zoom: 1 }}
        onInit={(instance) => {
          if (containerRef.current) {
            const svg = containerRef.current.querySelector('svg');
            if (svg) svgRef.current = svg as SVGSVGElement;
          }
        }}
      >
        <Controls />
        <Background color="#f3f4f6" gap={16} />
      </ReactFlow>

      {/* Right Drawer */}
      <div className={`right-drawer ${isDrawerOpen ? 'open' : ''}`}>
        <div
          className="drawer-toggle"
          onClick={() => setIsDrawerOpen(!isDrawerOpen)}
        >
          <PanelRight size={20} />
        </div>

        {isDrawerOpen && selectedData && (
          <div className="drawer-content">
            <div className="drawer-header">
              <h3>
                {selectedData.type === 'node' ? 'Node Details' : 'Edge Details'}
              </h3>
            </div>
            <div className="drawer-body">
              {selectedData.type === 'node' ? (
                // Node Details
                <>
                  <div className="detail-row">
                    <span className="detail-label">Label:</span>
                    <span className="detail-value">
                      {selectedData.data.label || 'N/A'}
                    </span>
                  </div>
                  {selectedData.data.description && (
                    <div className="detail-row">
                      <span className="detail-label">Description:</span>
                      <span className="detail-value">
                        {selectedData.data.description}
                      </span>
                    </div>
                  )}
                  {selectedData.data.nodeType && (
                    <div className="detail-row">
                      <span className="detail-label">Type:</span>
                      <span className="detail-value">
                        {selectedData.data.nodeType}
                      </span>
                    </div>
                  )}
                  {selectedData.data.step && (
                    <div className="detail-row">
                      <span className="detail-label">Step:</span>
                      <span className="detail-value">
                        {selectedData.data.step}
                      </span>
                    </div>
                  )}
                  {selectedData.data.time && (
                    <div className="detail-row">
                      <span className="detail-label">Time:</span>
                      <span className="detail-value">
                        {new Date(
                          selectedData.data.time * 1000,
                        ).toLocaleString()}
                      </span>
                    </div>
                  )}
                  {selectedData.data.icon && (
                    <div className="detail-row">
                      <span className="detail-label">Icon:</span>
                      <span className="detail-value">
                        {selectedData.data.icon}
                      </span>
                    </div>
                  )}
                </>
              ) : (
                // Edge Details
                <>
                  <div className="detail-row">
                    <span className="detail-label">ID:</span>
                    <span className="detail-value">
                      {selectedData.data.id || 'N/A'}
                    </span>
                  </div>
                  {selectedData.data.source && (
                    <div className="detail-row">
                      <span className="detail-label">Source:</span>
                      <span className="detail-value">
                        {selectedData.data.source}
                      </span>
                    </div>
                  )}
                  {selectedData.data.target && (
                    <div className="detail-row">
                      <span className="detail-label">Target:</span>
                      <span className="detail-value">
                        {selectedData.data.target}
                      </span>
                    </div>
                  )}
                  {selectedData.data.label && (
                    <div className="detail-row">
                      <span className="detail-label">Label:</span>
                      <span className="detail-value">
                        {selectedData.data.label}
                      </span>
                    </div>
                  )}
                  {selectedData.data.step && (
                    <div className="detail-row">
                      <span className="detail-label">Step:</span>
                      <span className="detail-value">
                        {selectedData.data.step}
                      </span>
                    </div>
                  )}
                  {selectedData.data.time && (
                    <div className="detail-row">
                      <span className="detail-label">Time:</span>
                      <span className="detail-value">
                        {new Date(
                          selectedData.data.time * 1000,
                        ).toLocaleString()}
                      </span>
                    </div>
                  )}

                  {selectedData.data?.details?.input_args &&
                    Array.isArray(selectedData.data.details.input_args) &&
                    selectedData.data.details.input_args.length > 0 && (
                      <>
                        <div className="detail-row">
                          <span className="detail-label">Inputs</span>
                          <span
                            className="detail-value"
                            style={{ overflowY: 'auto', maxHeight: '300px' }}
                          >
                            {Array.isArray(
                              selectedData.data.details.input_args[0],
                            ) ? (
                              selectedData.data.details.input_args[0].map(
                                (arg: any, index: number) => (
                                  <div
                                    key={arg?.role || index}
                                    style={{ marginBottom: 8 }}
                                  >
                                    <span className="detail-label">Role:</span>
                                    <span className="detail-value">
                                      {arg?.role || 'Unknown'}
                                    </span>
                                    <span className="detail-label">
                                      Content:
                                    </span>
                                    <span className="detail-value">
                                      {arg?.content || 'No content'}
                                    </span>
                                  </div>
                                ),
                              )
                            ) : (
                              <span className="detail-value">
                                {JSON.stringify(
                                  selectedData.data.details.input_args[0],
                                  null,
                                  2,
                                )}
                              </span>
                            )}
                          </span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Outputs</span>
                          <span className="detail-value">
                            {JSON.stringify(
                              selectedData.data?.details?.output,
                              null,
                              2,
                            )}
                          </span>
                        </div>
                      </>
                    )}
                </>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Timeline */}
      {showTimelines && (
        <div style={{ marginLeft: '280px', marginTop: '100px' }}>
          <Timeline
            stamps={flowData.stamps || flowData.steps || []}
            currentStep={currentStep}
            isPlaying={isPlaying}
            onStepChange={handleStepChange}
            onPlayPause={handlePlayPause}
          />
        </div>
      )}

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

          /* Right Drawer Styles */
          .right-drawer {
            position: absolute;
            top: 0;
            right: 0;
            height: 100%;
            z-index: 1000;
            display: flex;
            align-items: flex-start;
            transition: transform 0.3s ease;
            margin-left: ${
              showTimelines ? '280px' : '0'
            }; /* Account for vertical timeline when visible */
          }

          .right-drawer:not(.open) {
            transform: translateX(calc(100% - 50px));
          }

          .right-drawer.open {
            transform: translateX(0);
          }

          .drawer-toggle {
            width: 50px;
            height: 50px;
            background: none;
            color: #6b7280;
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: color 0.2s ease;
            margin-top: 20px;
          }

          .drawer-toggle:hover {
            color: #374151;
          }

          .drawer-content {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px 0 0 8px;
            width: 400px;
            height: calc(100% - 40px);
            margin-top: 20px;
            display: flex;
            flex-direction: column;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            animation: drawerSlideIn 0.3s ease-out;
          }

          .drawer-header {
            padding: 16px 20px;
            border-bottom: 1px solid #e5e7eb;
            background: #f9fafb;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
          }

          .drawer-header h3 {
            margin: 0;
            font-size: 16px;
            font-weight: 600;
            color: #1f2937;
          }

          .close-button {
            background: none;
            border: none;
            font-size: 20px;
            color: #6b7280;
            cursor: pointer;
            padding: 4px;
            width: 28px;
            height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 6px;
            transition: all 0.2s ease;
          }

          .close-button:hover {
            background: #e5e7eb;
            color: #1f2937;
          }

          .drawer-body {
            padding: 20px;
            overflow-y: auto;
            flex: 1;
            width: 100%;
            box-sizing: border-box;
          }

          .detail-row {
            display: grid;
            grid-template-columns: 100px 1fr;
            margin-bottom: 12px;
            align-items: flex-start;
            gap: 8px;
          }

          .detail-row:last-child {
            margin-bottom: 0;
          }

          .detail-label {
            font-weight: 600;
            color: #6b7280;
            font-size: 13px;
            word-break: break-word;
          }

          .detail-value {
            color: #1f2937;
            font-size: 13px;
            word-break: break-word;
            flex: 1;
            width: 100%;
            overflow: visible;
            text-overflow: unset;
            max-width: unset;
            white-space: pre-line;
            line-height: 1.4;
          }

          @keyframes drawerSlideIn {
            from {
              opacity: 0;
              transform: translateX(20px);
            }
            to {
              opacity: 1;
              transform: translateX(0);
            }
          }

          /* Scoreboard Styles */
          .scoreboard {
            position: absolute;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            z-index: 1000;
            min-width: 400px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          }

          .scoreboard-header {
            padding: 12px 16px;
            border-bottom: 1px solid #e5e7eb;
            background: #f9fafb;
            text-align: center;
          }

          .scoreboard-header h3 {
            margin: 0;
            font-size: 14px;
            font-weight: 600;
            color: #1f2937;
          }

          .scoreboard-content {
            padding: 16px;
            display: flex;
            justify-content: space-around;
            align-items: center;
            gap: 20px;
          }

          .scoreboard-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
          }

          .scoreboard-label {
            font-size: 12px;
            color: #6b7280;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
          }

          .scoreboard-count {
            font-size: 18px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 6px;
            min-width: 40px;
            text-align: center;
          }

          .scoreboard-count.open {
            background: #fef3c7;
            color: #92400e;
          }

          .scoreboard-count.completed {
            background: #d1fae5;
            color: #065f46;
          }

          .scoreboard-count.error {
            background: #fee2e2;
            color: #991b1b;
          }

          .scoreboard-count.error.clickable {
            transition: all 0.2s ease;
          }

          .scoreboard-count.error.clickable:hover {
            background: #fecaca;
            transform: scale(1.05);
            box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
          }

          /* Side Panel Styles */
          .side-panel {
            position: absolute;
            top: 0;
            left: 0;
            height: 100%;
            z-index: 1000;
            display: flex;
            flex-direction: column;
            transition: all 0.3s ease;
          }

          .side-panel.collapsed {
            width: 60px;
          }

          .side-panel.expanded {
            width: 280px;
          }

          .panel-toggle {
            display: flex;
            align-items: center;
            justify-content: center;
            border: none;
            background: none;
            cursor: pointer;
            color: #6b7280;
            transition: color 0.2s ease;
            padding: 8px;
            margin: 20px 0 0 0;
          }

          .panel-toggle:hover {
            color: #374151;
          }

          .panel-content {
            flex: 1;
            background: white;
            border-right: 1px solid #e5e7eb;
            box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
            overflow: hidden;
          }
        `}
      </style>
    </div>
  );
};

export default AgenticFlowVisualizer;
