import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import MyComponent from './MyComponent';
import { ReactFlowProvider } from 'reactflow';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

const root = createRoot(rootElement);

root.render(
  <StrictMode>
    <ReactFlowProvider>
      <MyComponent />
    </ReactFlowProvider>
  </StrictMode>,
);
