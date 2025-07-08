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
  onInspect?: (edgeData: any) => void;
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
  onInspect,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  // Function to determine stroke color based on edge state
  const getStrokeColor = () => {
    const state = data?.details?.state;
    switch (state) {
      case 'Open':
        return '#000000'; // Black
      case 'Completed':
        return '#15803d'; // Darker Green
      case 'Error':
        return '#ef4444'; // Red
      default:
        return style.stroke || '#6366f1'; // Default color
    }
  };

  const [edgePath, arrowMarkers] = useMemo(() => {
    const centerX = (sourceX + targetX) / 2;
    const centerY = (sourceY + targetY) / 2;
    const path = `M ${sourceX} ${sourceY} Q ${centerX} ${centerY} ${targetX} ${targetY}`;

    // Create arrow markers for bidirectional edges
    const markers = [];
    if (bidirectional) {
      const strokeColor = getStrokeColor();
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
    data?.details?.state,
  ]);

  const hoverStyle = {
    ...style,
    stroke: getStrokeColor(),
    strokeWidth: style.strokeWidth || 4,
    cursor: 'pointer',
  };

  const handleInspectClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (onInspect && data) {
      onInspect(data);
    }
  };

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
              onClick={handleInspectClick}
              style={{
                background: '#6366f1',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                padding: '4px 12px',
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 2px 8px rgba(99,102,241,0.10)',
                transition: 'background 0.2s',
              }}
            >
              Inspect
            </button>
          </div>
        </foreignObject>
      )}

      <style>
        {`
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
