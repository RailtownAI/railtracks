# Guardrails Overview

Guardrails are a policy layer around agent execution. They inspect requests before they reach a model and responses before they are returned, letting you enforce rules for safety, reliability, and product behavior.

Guardrails aren't just about blocking unsafe content. They can also:

- Normalize inputs
- Redact sensitive data
- Enforce domain limits
- Shape outputs in a controlled, observable way

## Categories

Railtracks organizes guardrails into four categories covering the full lifecycle of an agent run:

- **LLM input guardrails**: inspect messages before the model call
- **LLM output guardrails**: inspect the model response before it is returned

## Usage

Guardrails are attached through the `middleware` API. Please see the [Middleware](../overview.md#attaching-middleware) documentation for more details. 

## Prebuilt Guards
We have a set of prebuilt guardrails for common use cases. Check out the complete list of [prebuilt guardrails](prebuilt/overview.md). 

## Custom Guards
TBD see changed from @pooria 

The next section, [Quickstart](quickstart.md), walks through attaching a guard to an agent and seeing a request pass or block in practice.
