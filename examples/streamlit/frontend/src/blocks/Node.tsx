import React, { useState } from 'react';
import { Handle, Position } from 'reactflow';

interface NodeData {
  label: string;
  description?: string;
  nodeType?: string;
  step?: number;
  time?: number;
  icon?: string;
}

const Node: React.FC<{ data: NodeData }> = ({ data }) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <>
      <div
        className="agent-node"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
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
        <Handle
          type="source"
          position={Position.Right}
          style={{ background: '#6366f1' }}
        />

        {/* Side Popover */}
        {isHovered && (
          <div className="node-popover">
            <div className="popover-header">
              <h3>Node Details</h3>
            </div>
            <div className="popover-content">
              <div className="detail-row">
                <span className="detail-label">Label:</span>
                <span className="detail-value">{data.label}</span>
              </div>
              {data.description && (
                <div className="detail-row">
                  <span className="detail-label">Description:</span>
                  <span className="detail-value">{data.description}</span>
                </div>
              )}
              {data.nodeType && (
                <div className="detail-row">
                  <span className="detail-label">Type:</span>
                  <span className="detail-value">{data.nodeType}</span>
                </div>
              )}
              {data.step && (
                <div className="detail-row">
                  <span className="detail-label">Step:</span>
                  <span className="detail-value">{data.step}</span>
                </div>
              )}
              {data.time && (
                <div className="detail-row">
                  <span className="detail-label">Time:</span>
                  <span className="detail-value">
                    {new Date(data.time * 1000).toLocaleString()}
                  </span>
                </div>
              )}
              {data.icon && (
                <div className="detail-row">
                  <span className="detail-label">Icon:</span>
                  <span className="detail-value">{data.icon}</span>
                </div>
              )}
            </div>
          </div>
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

          /* Popover Styles */
          .node-popover {
            position: absolute;
            left: calc(100% + 12px);
            top: 0;
            width: 280px;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
            z-index: 8001;
            animation: popoverFadeIn 0.2s ease-out;
          }

          .node-popover::before {
            content: '';
            position: absolute;
            left: -6px;
            top: 20px;
            width: 0;
            height: 0;
            border-top: 6px solid transparent;
            border-bottom: 6px solid transparent;
            border-right: 6px solid #e5e7eb;
          }

          .node-popover::after {
            content: '';
            position: absolute;
            left: -5px;
            top: 20px;
            width: 0;
            height: 0;
            border-top: 6px solid transparent;
            border-bottom: 6px solid transparent;
            border-right: 6px solid white;
          }

          .popover-header {
            padding: 12px 16px;
            border-bottom: 1px solid #e5e7eb;
            background: #f9fafb;
            border-radius: 8px 8px 0 0;
          }

          .popover-header h3 {
            margin: 0;
            font-size: 14px;
            font-weight: 600;
            color: #1f2937;
          }

          .popover-content {
            padding: 16px;
          }

          .detail-row {
            display: flex;
            margin-bottom: 8px;
            align-items: flex-start;
          }

          .detail-row:last-child {
            margin-bottom: 0;
          }

          .detail-label {
            font-weight: 600;
            color: #6b7280;
            font-size: 12px;
            min-width: 80px;
            margin-right: 8px;
          }

          .detail-value {
            color: #1f2937;
            font-size: 12px;
            word-break: break-word;
            flex: 1;
          }

          @keyframes popoverFadeIn {
            from {
              opacity: 0;
              transform: translateX(-10px);
            }
            to {
              opacity: 1;
              transform: translateX(0);
            }
          }
        `}
      </style>
    </>
  );
};

export { Node };
export type { NodeData };
