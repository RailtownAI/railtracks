# Node Building

The Node Building component is a flexible utility designed to facilitate the dynamic creation of node subclasses with custom configurations. It supports interactions with Language Learning Models (LLMs) and tools, allowing developers to programmatically construct new node classes with specific overrides and configurations.

**Version:** 0.0.1

**Component Contact:** @developer_username

## Table of Contents

- [1. Purpose](#1-purpose)
- [2. Public API](#2-public-api)
- [3. Architectural Design](#3-architectural-design)
- [4. Important Considerations](#4-important-considerations)
- [5. Related Files](#5-related-files)
- [CHANGELOG](#changelog)

## 1. Purpose

The Node Building component is primarily used to create customized node subclasses within the railtracks framework. This is particularly useful for scenarios where small modifications to existing classes like ToolCalling, Structured, or Terminal LLMs are needed. The component allows for the overriding of methods and attributes such as pretty names, tool details, parameters, and LLM configurations.

### 1.1 Dynamic Node Creation

The primary use case for the Node Building component is the dynamic creation of node subclasses. This is important for developers who need to extend the functionality of existing node classes without modifying the original class definitions.

python
from railtracks.nodes import NodeBuilder, Node

class CustomNode(Node):
    pass

builder = NodeBuilder(CustomNode, name="Custom Node", class_name="DynamicCustomNode")
custom_node_class = builder.build()


### 1.2 LLM Configuration

Another significant use case is configuring nodes to interact with specific LLM models and system messages. This is crucial for applications that require tailored LLM interactions.

python
from railtracks.llm import ModelBase, SystemMessage

builder.llm_base(llm_model=ModelBase(), system_message="Custom system message")


## 2. Public API



## 3. Architectural Design

### 3.1 NodeBuilder Class

- **Design Consideration:** The `NodeBuilder` class is designed to be generic, allowing it to work with any subclass of `Node`. This flexibility is achieved through the use of Python's generics and type variables.
- **Logic Flow:** The `NodeBuilder` class maintains a dictionary of method overrides, which are applied to the dynamically created node subclass. This allows for the customization of node behavior without altering the original class definitions.
- **Core Philosophy:** The component adheres to the principle of separation of concerns by isolating the node creation logic from the node's operational logic.

## 4. Important Considerations

### 4.1 Method Overrides

- **Non-Obvious Detail:** When overriding methods using the `NodeBuilder`, existing methods with the same name will be replaced. This can lead to unexpected behavior if not managed carefully.
- **Critical Detail:** The `build` method constructs the final node subclass, applying all configured overrides. It is essential to ensure that all necessary configurations are set before calling this method.

## 5. Related Files

### 5.1 Code Files

- [`../_node_builder.py`](../_node_builder.py): Contains the implementation of the NodeBuilder class and its methods.

### 5.2 Related Component Files

- [Node Interaction Documentation](../components/node_interaction.md): Explains how nodes interact within the railtracks framework.

### 5.3 Related Feature Files

- [Node Management Documentation](../features/node_management.md): Details the management and lifecycle of nodes within the system.

## CHANGELOG

- **v0.0.1** (YYYY-MM-DD) [`<COMMIT_HASH>`]: Initial version.
