# Request Completion Agentic Framework (RC)

## Overview

The Request Completion framework is a system designed to allow you to build simple Agentic systems that can be used to
accomplish complicated tasks. By building "agents" with specialized abilities you can accomplish much more complicated
tasks that single module could accomplish. Although the system is designed from the standpoint of LLMs being those agents,
it is flexible and the idea of an agent could be any peice of modular functionality.

The framework is designed to support the building, testing, debugging, and deployment of
such systems. It's core principle of the system follows from a Request and Completion model where the actions are single
modular components. Each modular component has the ability to answer the upstream query or open a new downstream request
to another modular component.

## Key Features

- **Automatic Parallelism** - The system will automatically parallelize the execution of the modular components.
- **Streaming Capability** - By defining what you want to stream and attaching a handler you can stream updates to the
  system via a callback mechanism.
- **Error Handling** - The system has a 3 tiered error handling approach that allows you to handle errors with grace to
  keep your application up and running.
- **Debugging** - The system has built in debugging tools that will allow you to inspect flows to understand what is
  going on in your application.
- **Control Flow Definition** - The system allows you to define the exact allowed flows between your modular components.
- **Automatic Mapping of Linear Flows into RC** - The system will automatically map a simple linear flow to work within
  the RC framework.

## Getting Started

In the below section, I will walk you through the steps on how to get started using the request completion framework.

### Step 1: Install the Library

```bash
pip install requestcompletion
```

Or add it to your requirements.txt.

### Step 2: Define your Modular Components

```python

```

### Step 3: Define your Control Flow

```python

```

### Step 4: Run your Application

```python

```

## Contributing

See the [contributing guide](./CONTRIBUTING.md) for more information.
