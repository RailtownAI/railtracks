import React, { useEffect, useRef } from 'react';

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

  // Initialize Bootstrap tooltips
  useEffect(() => {
    // Initialize all tooltips
    const tooltipTriggerList = document.querySelectorAll(
      '[data-bs-toggle="tooltip"]',
    );
    const tooltipList = Array.from(tooltipTriggerList).map(
      (tooltipTriggerEl) =>
        new (window as any).bootstrap.Tooltip(tooltipTriggerEl),
    );

    // Cleanup function to dispose tooltips
    return () => {
      tooltipList.forEach((tooltip) => tooltip.dispose());
    };
  }, [stamps, currentStep]); // Re-initialize when stamps or currentStep changes

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
          const isPast = step < currentStep;
          const hasStep = stamps.some((s) => s.step === step);

          // Determine background color based on step state
          let backgroundColor = 'white';
          if (isActive) {
            backgroundColor = '#6366f1';
          } else if (isPast) {
            backgroundColor = hasStep ? '#fef3c7' : '#fef3c7'; // Light yellow for past steps
          } else if (hasStep) {
            backgroundColor = '#e5e7eb';
          }

          const tooltipText = `Step ${step}${
            hasStep
              ? ` - ${stamps.find((s) => s.step === step)?.identifier || ''}`
              : ' - No activity'
          }`;

          return (
            <button
              key={step}
              onClick={() => onStepChange(step)}
              data-bs-toggle="tooltip"
              data-bs-placement="top"
              data-bs-title={tooltipText}
              style={{
                width: '16px',
                height: '16px',
                borderRadius: '50%',
                border: isActive ? '2px solid #6366f1' : '1px solid #d1d5db',
                backgroundColor: backgroundColor,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                position: 'relative',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  if (isPast) {
                    e.currentTarget.style.backgroundColor = hasStep
                      ? '#fde68a'
                      : '#fde68a'; // Darker yellow on hover for past steps
                  } else {
                    e.currentTarget.style.backgroundColor = hasStep
                      ? '#d1d5db'
                      : '#f3f4f6';
                  }
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  if (isPast) {
                    e.currentTarget.style.backgroundColor = hasStep
                      ? '#fef3c7'
                      : '#fef3c7'; // Back to light yellow for past steps
                  } else {
                    e.currentTarget.style.backgroundColor = hasStep
                      ? '#e5e7eb'
                      : 'white';
                  }
                }
              }}
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

export { Timeline };
