import React from 'react';

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

export { Timeline };
