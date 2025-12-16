Testing has been an essential part of the software engineering lifecycle. While "Agents" are still software products, due to being stochastic in nature, they require to also be evaluated from certain other paradigms. Evaluation of AI Agents is an active area of research with currently no widespread agreed upon standards. In **Railtracks** we follow the philosophy of continuing to allow flexibility for users to define what "Evaluation of Agents" means to them.

We have set the structural outline below of two potential avenues for evaluations:

1. Evaluations that require an agent to be invoked

2. Evaluations that analyze the past results of an agent

While this results in a nice seperation between potential cases, there are some cases that have elements of both which we will expand on further in the specific sections regarding usage.

## Evaluation Flow

```mermaid
graph TD
    Developer([Developer]) --> BuildAgent[Agent Build]
    
    BuildAgent --> Dataset[Dataset]
    
    subgraph Evaluation ["Evaluation Pipeline"]
        Dataset --> Evaluator[Evaluator]
        Evaluator --> Metric[Metric]
        Metric --> Result[Result]
    end
    
    Result -->|Iterate & Improve| BuildAgent

    Result --> Deploy[Deployment]
    Deploy --> |User Feedback| BuildAgent
    
    %% === COLOR THEMING ===
    %% Define color classes based on consistent theme
    classDef userClass fill:#60A5FA,fill-opacity:0.3
    classDef buildClass fill:#FBBF24,fill-opacity:0.3
    classDef evalClass fill:#34D399,fill-opacity:0.3
    classDef resultClass fill:#BFDBFE,fill-opacity:0.3
    classDef pipelineClass fill:#FECACA,fill-opacity:0.3
    classDef deployClass fill:#34D399 ,fill-opacity:0.3
    
    %% Apply color classes
    class User userClass;
    class BuildAgent buildClass;
    class Dataset,Evaluator,Metric pipelineClass;
    class Result resultClass;
    class Deploy deployClass;

    %% Subgraph style
    style Evaluation fill:transparent,stroke:#FFFFF,stroke-width:1px
```
