declare module '*.json' {
  const value: {
    nodes: Array<{
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
            input_tokens: number;
            output_tokens: number;
            total_cost: number;
            system_fingerprint: string;
          }>;
          latency?: {
            total_time: number;
          };
        };
      };
      parent: {
        identifier: string;
        node_type: string;
        stamp: {
          step: number;
          time: number;
          identifier: string;
        };
        details: {
          internals?: any;
        };
        parent: any;
      } | null;
    }>;
    edges: Array<{
      identifier: string;
      source: string | null;
      target: string;
      stamp: {
        step: number;
        time: number;
        identifier: string;
      };
      details: {
        input_args?: any[];
        input_kwargs?: any;
        output?: any;
      };
      parent: {
        source: string | null;
        target: string;
        identifier: string;
        stamp: {
          step: number;
          time: number;
          identifier: string;
        };
        details: {
          input_args?: any[];
          input_kwargs?: any;
          output?: any;
        };
        parent: any;
      } | null;
    }>;
    stamps: Array<{
      step: number;
      time: number;
      identifier: string;
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
