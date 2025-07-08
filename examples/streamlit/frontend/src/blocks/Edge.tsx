import React, { useMemo, useState, useEffect } from 'react';

interface EdgeProps {
  id: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  sourcePosition: any;
  targetPosition: any;
  style?: React.CSSProperties;
  markerEnd?: string;
  bidirectional?: boolean;
  data?: {
    label?: string;
    source?: string;
    target?: string;
    step?: number;
    time?: number;
    details?: any;
  };
  clientToSvgCoords?: (
    clientX: number,
    clientY: number,
  ) => { x: number; y: number };
  svgRef?: React.RefObject<SVGSVGElement>;
}

const Edge: React.FC<EdgeProps> = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  bidirectional = false,
  data,
  clientToSvgCoords,
  svgRef,
}) => {
  const [isHovered, setIsHovered] = useState(false);
  const [isClicked, setIsClicked] = useState(false);
  const [clickPosition, setClickPosition] = useState({ x: 0, y: 0 });

  // Handle click outside to close the panel
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // Check if the click is outside the edge path and outside the drawer
      const target = event.target as Element;
      const isInsideEdge = target.closest(`[data-edge-id="${id}"]`);
      const isInsideDrawer = target.closest('.edge-drawer');

      if (!isInsideEdge && !isInsideDrawer) {
        setIsClicked(false);
      }
    };

    if (isClicked) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isClicked, id]);

  const [edgePath, arrowMarkers] = useMemo(() => {
    const centerX = (sourceX + targetX) / 2;
    const centerY = (sourceY + targetY) / 2;
    const path = `M ${sourceX} ${sourceY} Q ${centerX} ${centerY} ${targetX} ${targetY}`;

    // Create arrow markers for bidirectional edges
    const markers = [];
    if (bidirectional) {
      const strokeColor = isClicked ? '#10b981' : style.stroke || '#6366f1';
      // Forward arrow (source to target)
      markers.push(
        <defs key={`${id}-markers`}>
          <marker
            id={`${id}-arrowhead-forward`}
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill={strokeColor} />
          </marker>
          <marker
            id={`${id}-arrowhead-backward`}
            markerWidth="10"
            markerHeight="7"
            refX="1"
            refY="3.5"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <polygon points="10 0, 0 3.5, 10 7" fill={strokeColor} />
          </marker>
        </defs>,
      );
    }

    return [path, markers];
  }, [
    sourceX,
    sourceY,
    targetX,
    targetY,
    id,
    bidirectional,
    style.stroke,
    isHovered,
    isClicked,
  ]);

  const hoverStyle = {
    ...style,
    stroke: isClicked ? '#10b981' : style.stroke,
    strokeWidth: isClicked
      ? (Number(style.strokeWidth) || 4) + 1
      : style.strokeWidth || 4,
    cursor: 'pointer',
  };

  const handleEdgeClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (clientToSvgCoords) {
      setClickPosition(clientToSvgCoords(event.clientX, event.clientY));
    } else {
      setClickPosition({ x: event.clientX, y: event.clientY });
    }
    setIsClicked(!isClicked);
  };

  const shouldShowPanel = isClicked;
  const stateLabel = data?.details?.state || 'Open'; // Completed | Open
  return (
    <g data-edge-id={id}>
      {arrowMarkers}
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        markerEnd={bidirectional ? `url(#${id}-arrowhead-forward)` : markerEnd}
        markerStart={
          bidirectional ? `url(#${id}-arrowhead-backward)` : undefined
        }
        style={hoverStyle}
        onClick={handleEdgeClick}
      />

      {/* Edge Label Renderer */}
      {data?.label && (
        <foreignObject
          x={(sourceX + targetX) / 2 - 50}
          y={(sourceY + targetY) / 2 - 20}
          width="100"
          height="40"
          style={{ overflow: 'visible', pointerEvents: 'none' }}
        >
          <div
            className="edge-label-renderer"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              height: '100%',
              pointerEvents: 'auto',
            }}
          >
            <button
              className="edge-label-button"
              onClick={(e) => {
                e.stopPropagation();
                setIsClicked(true);
              }}
              style={{
                background: isClicked ? '#10b981' : '#6366f1',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                padding: '4px 12px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: isClicked
                  ? '0 2px 8px rgba(16,185,129,0.15)'
                  : '0 2px 8px rgba(99,102,241,0.10)',
                transition: 'background 0.2s',
                outline: isClicked ? '2px solid #10b981' : 'none',
              }}
            >
              Inspect
            </button>
          </div>
        </foreignObject>
      )}

      {/* Edge Detail Drawer */}
      {shouldShowPanel && data && (
        <foreignObject
          x={(sourceX + targetX) / 2 + 60}
          y={(sourceY + targetY) / 2 - 100}
          width="400"
          height="600"
          style={{ overflow: 'visible' }}
        >
          <div
            className={`edge-drawer ${isClicked ? 'persistent' : ''} ${
              stateLabel === 'Completed' ? 'completed' : ''
            }`}
          >
            <div className="drawer-header">
              <h3>Edge Details ({stateLabel})</h3>
              {isClicked && (
                <button
                  className="close-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsClicked(false);
                  }}
                >
                  ×
                </button>
              )}
            </div>
            <div className="drawer-content">
              <div className="detail-row">
                <span className="detail-label">ID:</span>
                <span className="detail-value">{id}</span>
              </div>
              {data.source && (
                <div className="detail-row">
                  <span className="detail-label">Source:</span>
                  <span className="detail-value">{data.source}</span>
                </div>
              )}
              {data.target && (
                <div className="detail-row">
                  <span className="detail-label">Target:</span>
                  <span className="detail-value">{data.target}</span>
                </div>
              )}
              {data.label && (
                <div className="detail-row">
                  <span className="detail-label">Label:</span>
                  <span className="detail-value">{data.label}</span>
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

              {data?.details?.input_args &&
                Array.isArray(data.details.input_args) &&
                data.details.input_args.length > 0 && (
                  <>
                    <div className="detail-row">
                      <span className="detail-label">Inputs</span>
                      <span
                        className="detail-value"
                        style={{ overflowY: 'auto', maxHeight: '300px' }}
                      >
                        {Array.isArray(data.details.input_args[0]) ? (
                          data.details.input_args[0].map(
                            (arg: any, index: number) => (
                              <div
                                key={arg?.role || index}
                                style={{ marginBottom: 8 }}
                              >
                                <span className="detail-label">Role:</span>
                                <span className="detail-value">
                                  {arg?.role || 'Unknown'}
                                </span>
                                <span className="detail-label">Content:</span>
                                <span className="detail-value">
                                  {arg?.content || 'No content'}
                                </span>
                              </div>
                            ),
                          )
                        ) : (
                          <span className="detail-value">
                            {JSON.stringify(
                              data.details.input_args[0],
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
                        {JSON.stringify(data?.details?.output, null, 2)}
                      </span>
                    </div>
                  </>
                )}

              {/* {data.details && (
                <div className="detail-row">
                  <span className="detail-label">Details:</span>
                  <span className="detail-value">
                    {JSON.stringify(data.details, null, 2)}
                  </span>
                </div>
              )} */}
            </div>
          </div>
        </foreignObject>
      )}

      <style>
        {`
          .edge-drawer {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 4px 25px rgba(0, 0, 0, 0.15);
            z-index: 8001;
            animation: drawerSlideIn 0.3s ease-out;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            height: 600px;
            display: flex;
            flex-direction: column;
            position: relative;
            max-height: 80vh;
          }

          .edge-drawer.persistent {
            border-color: #10b981;
            box-shadow: 0 4px 25px rgba(16, 185, 129, 0.15);
          }

          .edge-drawer.completed {
            border-color: #10b981;
            box-shadow: 0 4px 25px rgba(16, 185, 129, 0.15);
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

          .drawer-content {
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
              transform: scale(0.95) translateY(-10px);
            }
            to {
              opacity: 1;
              transform: scale(1) translateY(0);
            }
          }

          .edge-label-renderer {
            z-index: 8001;
            user-select: none;
            pointer-events: auto;
          }

          .edge-label-button {
            pointer-events: auto;
          }
        `}
      </style>
    </g>
  );
};

export { Edge };
