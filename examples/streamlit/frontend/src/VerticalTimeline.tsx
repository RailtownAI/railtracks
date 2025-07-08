import React from 'react';

// ============================================================================
// VERTICAL TIMELINE COMPONENT
// ============================================================================

interface VerticalTimelineProps {
  stamps: Array<{
    step: number;
    time: number;
    identifier: string;
  }>;
  currentStep: number;
  onStepChange: (step: number) => void;
}

const VerticalTimeline: React.FC<VerticalTimelineProps> = ({
  stamps,
  currentStep,
  onStepChange,
}) => {
  const maxStep =
    stamps.length > 0 ? Math.max(...stamps.map((s) => s.step)) : 0;
  const minStep =
    stamps.length > 0 ? Math.min(...stamps.map((s) => s.step)) : 0;
  const totalSteps = maxStep - minStep + 1;

  // Calculate latency for each step
  const getStepLatency = (step: number) => {
    const stepStamps = stamps.filter((s) => s.step === step);
    if (stepStamps.length === 0) return null;

    // Calculate time difference from previous step
    const prevStep = step - 1;
    const prevStepStamps = stamps.filter((s) => s.step === prevStep);

    if (prevStepStamps.length === 0) return null;

    const currentTime = Math.min(...stepStamps.map((s) => s.time));
    const prevTime = Math.max(...prevStepStamps.map((s) => s.time));

    return currentTime - prevTime;
  };

  // Get step label
  const getStepLabel = (step: number) => {
    const stepStamps = stamps.filter((s) => s.step === step);
    if (stepStamps.length === 0) return `Step ${step}`;

    // Get the first identifier for this step
    const identifier = stepStamps[0]?.identifier || '';
    return identifier || `Step ${step}`;
  };

  // Format latency
  const formatLatency = (latency: number) => {
    if (latency < 1000) {
      return `${latency.toFixed(0)}ms`;
    } else if (latency < 60000) {
      return `${(latency / 1000).toFixed(1)}s`;
    } else {
      return `${(latency / 60000).toFixed(1)}m`;
    }
  };

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        width: '280px',
        height: '100%',
        backgroundColor: 'white',
        borderRight: '1px solid #e5e7eb',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 10,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '16px',
          borderBottom: '1px solid #e5e7eb',
          backgroundColor: '#f9fafb',
        }}
      >
        <h3
          style={{
            margin: 0,
            fontSize: '16px',
            fontWeight: 600,
            color: '#1f2937',
          }}
        >
          Timeline
        </h3>
        <p
          style={{
            margin: '4px 0 0 0',
            fontSize: '12px',
            color: '#6b7280',
          }}
        >
          Click to jump to step
        </p>
      </div>

      {/* Steps List */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 0',
        }}
      >
        {Array.from({ length: totalSteps }, (_, index) => {
          const step = minStep + index;
          const isActive = step === currentStep;
          const isPast = step < currentStep;
          const hasStep = stamps.some((s) => s.step === step);
          const latency = getStepLatency(step);
          const label = getStepLabel(step);

          return (
            <div
              key={step}
              onClick={() => hasStep && onStepChange(step)}
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid #f3f4f6',
                cursor: hasStep ? 'pointer' : 'default',
                backgroundColor: isActive ? '#f0f9ff' : 'transparent',
                borderLeft: isActive
                  ? '4px solid #6366f1'
                  : '4px solid transparent',
                transition: 'all 0.2s ease',
                position: 'relative',
              }}
              onMouseEnter={(e) => {
                if (hasStep && !isActive) {
                  e.currentTarget.style.backgroundColor = '#f8fafc';
                }
              }}
              onMouseLeave={(e) => {
                if (hasStep && !isActive) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }
              }}
            >
              {/* Step indicator */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  marginBottom: '4px',
                }}
              >
                <div
                  style={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '50%',
                    backgroundColor: isActive
                      ? '#6366f1'
                      : isPast
                      ? '#fbbf24'
                      : hasStep
                      ? '#9ca3af'
                      : '#e5e7eb',
                    border: isActive
                      ? '2px solid #6366f1'
                      : '1px solid #d1d5db',
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: '14px',
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? '#1f2937' : '#6b7280',
                  }}
                >
                  Step {step}
                </span>
                {latency && (
                  <span
                    style={{
                      fontSize: '11px',
                      color: '#9ca3af',
                      backgroundColor: '#f3f4f6',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      marginLeft: 'auto',
                    }}
                  >
                    {formatLatency(latency)}
                  </span>
                )}
              </div>

              {/* Label */}
              <div
                style={{
                  fontSize: '13px',
                  color: hasStep ? '#1f2937' : '#9ca3af',
                  lineHeight: '1.4',
                  wordBreak: 'break-word',
                  fontStyle: hasStep ? 'normal' : 'italic',
                }}
              >
                {hasStep ? label : 'No activity'}
              </div>

              {/* Active indicator */}
              {isActive && (
                <div
                  style={{
                    position: 'absolute',
                    right: '8px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: '#6366f1',
                    animation: 'pulse 2s infinite',
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      <style>
        {`
          @keyframes pulse {
            0% {
              opacity: 1;
            }
            50% {
              opacity: 0.5;
            }
            100% {
              opacity: 1;
            }
          }
        `}
      </style>
    </div>
  );
};

export { VerticalTimeline };
