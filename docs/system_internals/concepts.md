# Core Concepts

## Node-Based Execution Model
- **Nodes**: Atomic units of work (functions, AI agents, tools)
- **Execution Graph**: Dynamic tree built during runtime
- **Call Semantics**: How nodes invoke other nodes

## Immutable State Architecture
- **Forest Data Structures**: Why trees, not graphs
- **Temporal Tracking**: Time-travel debugging capabilities
- **State Snapshots**: Point-in-time execution views

## Event-Driven Coordination
- **Request Lifecycle**: Creation → Execution → Completion
- **Message Types**: Success, Failure, Streaming, Fatal
- **Loose Coupling**: Components communicate via events only

## Session Isolation
- **Context Boundaries**: Each session is independent
- **Resource Management**: Automatic cleanup and lifecycle
- **Configuration Scoping**: Settings apply per-session