import React from 'react';
import { Handle, Position, useReactFlow } from 'reactflow';

interface NodeData {
  label: string;
  description?: string;
  nodeType?: string;
  step?: number;
  time?: number;
  icon?: string;
  onInspect?: (nodeData: any) => void;
  id?: string; // Add id for zoom functionality
  edges?: any[]; // Add edges to node data
}

interface NodeProps {
  data: NodeData;
  id: string;
}

const Node: React.FC<NodeProps> = ({ data, id }) => {
  const { fitView } = useReactFlow();

  // Check if this node has any outgoing edges (source edges)
  const hasOutgoingEdges =
    data.edges?.some((edge: any) => edge.source === id) || false;

  const handleNodeClick = () => {
    // Zoom to the node
    fitView({
      nodes: [{ id }],
      duration: 800,
      padding: 0.1,
      minZoom: 0.5,
      maxZoom: 1.5,
    });

    // Open inspection drawer
    if (data.onInspect) {
      data.onInspect({
        label: data.label,
        description: data.description,
        nodeType: data.nodeType,
        step: data.step,
        time: data.time,
        icon: data.icon,
      });
    }
  };

  return (
    <>
      <div
        className="agent-node"
        onClick={handleNodeClick}
        style={{ cursor: 'pointer' }}
      >
        <Handle
          type="target"
          position={Position.Left}
          style={{ background: '#6366f1' }}
        />
        <div className="agent-header">
          <div className="agent-icon">{data.icon || '📋'}</div>
          <div className="agent-label">{data.label}</div>
        </div>
        {data.description && (
          <div className="agent-description">{data.description}</div>
        )}
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
        {hasOutgoingEdges && (
          <Handle
            type="source"
            position={Position.Right}
            style={{ background: '#6366f1' }}
          />
        )}
      </div>

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
            z-index: -5;
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
        `}
      </style>
    </>
  );
};

export { Node };
export type { NodeData };
