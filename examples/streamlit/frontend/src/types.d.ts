declare module '*.json' {
  const value: {
    nodes: Array<{
      identifier: string;
      node_type: string;
      details: {
        stamp: {
          time: number;
          step: number;
          identifier: string;
        };
        details: any;
      };
    }>;
    edges: Array<{
      identifier: string;
      source: string | null;
      target: string;
      details: {
        stamp: {
          time: number;
          step: number;
          identifier: string;
        };
        input: any;
        output: any;
      };
    }>;
  };
  export default value;
}

// Streamlit component interface
interface StreamlitInterface {
  getComponentValue(): any;
  setComponentValue(value: any): void;
}

declare global {
  interface Window {
    parent: {
      Streamlit: StreamlitInterface;
    };
  }
}

export {};
