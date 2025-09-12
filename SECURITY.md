# Security Policy

This SECURITY.md describes safe usage, best practices, risk management and how to report vulnerabilities for the RailTracks project.

RailTracks is a lightweight, modular framework for building agentic systems. It orchestrates agents, tools, and LLM calls but does not itself provide infrastructure hardening, network egress controls, or secret management.

## Audience

- Developers (primary): secure development and operation of agentic systems
- Security/Compliance teams: risk identification and control points
- Operators/SREs: deployment, logging, and data handling considerations
- Researchers/Contributors: responsible disclosure and scope

## Scope

- In scope:
  - RailTracks core (PyPI: railtracks)
  - Optional CLI (railtracks-cli) and visualization features
  - First-party example/demo tools and MCP tools included in this repository
- Out of scope:
  - Third-party tools, user-authored tools, plugins, and examples outside this repository
  - LLM/model providers, inference endpoints, and cloud services you choose to integrate
  - Your runtime and hosting environment (OS, containers, Kubernetes, serverless)
  - Organization-specific data policies and compliance obligations

## What RailTracks Is and Is Not

- Is: a framework to compose agents, call tools, and interact with Machine Learning Models; provides logging, execution history, debugging tools, and a API with optional CLI and visualization.
- Is not: a security sandbox, a secrets manager, a network firewall, a model training framework or a data loss prevention system. RailTracks does not enforce allow/deny-lists for network/filesystem access and does not implement provider-side data privacy controls.

## Remote Artifacts and Remote Code

- Models and providers: RailTracks can work with many providers (via your selected model or service). If your chosen stack relies on third-party artifacts (models/weights), prefer formats designed to prevent arbitrary code execution (for example, safetensors) and avoid loading unsafe formats (for example, pickle) from untrusted sources.
- Remote code execution: Do not execute untrusted code or install untrusted tools/plugins. If you import tools or components from external repositories, review their source and supply chain before enabling them in agents. This extends to model-generated code.

## LLM/Provider Considerations

- Data privacy: Understand each provider’s data handling (retention, training usage, residency, access logs). Configure provider privacy settings to match your requirements.
- Policy and safety: Filter/validate user inputs according to your organization’s policy and each provider’s acceptable use policy. Treat LLM outputs as untrusted until validated.
- Prompt injection/jailbreaks: Adversarial inputs can cause tools to be misused. Use input/output validation, constrained tools, and minimal permissions according to provider suggestion.

## Tools, MCP, and Execution Safety

- First-party tools: This repository may include example/demo tools and an example sandbox for demonstration purposes. You must configure and operate in secure settings. 
- User/third-party tools: Tools run arbitrary Python code. Review, restrict, and sandbox them. Run with least privilege; prefer read-only or narrowly scoped access when possible.
- MCP: Connecting to third party MCP servers/tools extends the attack surface. Only connect to trusted endpoints and review tool capabilities and permissions. Place necessary check and filter on inputs/outputs

## Configuration and Data Handling

- Execution state directory:
  - RailTracks can persist execution data to a local `.railtracks` directory to aid debugging and visualization.
  - This data may include inputs/outputs, prompts/responses, intermediate messages, tool inputs/outputs, runtime traces, and potentially secrets/tokens if passed through messages or tool params.
  - This directory is not automatically cleaned or redacted.
  - Recommendations:
    - Do not deploy system on an untrusted host or share the directory with untrusted users.
    - Protect `.railtracks` with appropriate file permissions.
- Logging and telemetry:
  - Local logging may capture sensitive information (including prompts, tool I/O, and environment-derived values).
  - The CLI offers optional configuration to forward logs/execution data. Only enable forwarding when you have appropriate agreements and controls for the destination.
- Not a secret store:
  - Do not rely on RailTracks to protect secrets.
  - Inject provider/API keys via secure means (for example, environment variables or a proper secret manager).
  - Avoid printing or embedding secrets into logs, messages, or persisted state.
  - Avoid executing user or generated code in the same environment that has access to sensitive files or credentials.

## Security-Relevant Configuration Notes

Defaults (consult docs for the exact version you use; defaults may change):
- `save_state`: may be enabled to persist execution for debugging/visualization
- `logging_setting`: typically "REGULAR", this is the logging verbosity level

## Network Egress and Environment Security

- RailTracks does not enforce network allow/deny-lists. Control egress at your network, container, or host layer (for example, proxies, firewall rules, VPC egress controls).
- Run untrusted or experimental tools in isolated environments (containers/VMs) with:
  - Non-root users and minimal filesystem access
  - Limited outbound network access (only required endpoints)
  - Resource limits (CPU, memory, timeouts) to reduce DoS risk
- Consult your deployment platform’s guidance (for example, your cloud provider) for hardening recommendations.

## Risks and Example Misuse Scenarios (with Mitigations)

- Filesystem access:
  - Risk: An agent with file tools may read secrets or delete important files.
  - Mitigations: Restrict tools to a dedicated directory; isolate with containers/VMs; provide only read access when feasible.
- External APIs:
  - Risk: An agent with write-capable API keys may post or delete data.
  - Mitigations: Prefer read-only keys where possible; scope tokens to necessary endpoints; monitor usage.
- Databases:
  - Risk: Broad DB permissions allow destructive or exfiltration actions.
  - Mitigations: Use read-only roles for analytics; schema- or table-scoped credentials; audit logging/alerts.
- Prompt injection/jailbreaks:
  - Risk: User inputs steer models to misuse tools or leak data.
  - Mitigations: Validate/sanitize inputs; gate high-impact actions; require structured outputs and verify them before acting.
- Long-running tasks/automation:
  - Risk: Automation loops amplify mistakes.
  - Mitigations: Timeouts, rate limits, human-in-the-loop for critical actions, checkpoints/approvals for destructive operations.

## Dependency and Supply Chain Hygiene (for Deployers)

- Pin dependencies where practical and track upstream advisories for transitive libraries.
- Use your organization’s standard dependency/secret scanning and image scanning in CI/CD.
- Review third-party tools and MCP endpoints before integrating them into agents.

## Release Channels and Verification

- Official releases: PyPI (railtracks) and GitHub (source, tags).
- Verify you are installing from these official channels. Avoid untrusted mirrors or modified forks unless you have reviewed them.

## Reporting a Vulnerability

- Report suspected vulnerabilities privately to: [Security Email](mailto:security.railtracks@railtown.ai)
  - Do not open public GitHub issues for security reports.
  - Include a detailed description, affected versions, a proof of concept if available, and your contact info.
  - If your report involves third-party tools or providers, specify which components are affected.
- We do not currently operate a public bug-bounty program. Disclosure timelines and remediations may vary by severity.

## In-Scope for Security Reports

Vulnerabilities in the RailTracks core library, CLI, and first-party tools included in this repository that could lead to:
- Code execution, privilege escalation, or sandbox escape within the RailTracks process
- Unauthorized access or disclosure of data persisted by RailTracks (for example, `.railtracks`) when used as documented
- Integrity issues that allow an attacker to subvert tool invocation or agent routing without user authorization
- Documentation inaccuracies that materially mislead users about security behavior

## Out of Scope for Security Reports

- Misuse or insecure configuration of third-party tools, services, or providers
- Vulnerabilities in external LLM/model providers or MCP servers not maintained by this project
- Risks arising from user-authored tools or example code not included in this repository
- Insecure host or network environments, missing OS patches, or lack of hardening outside RailTracks
- Findings that require unrealistic attacker capabilities or non-default, undocumented configurations

## Open Source and Licensing Notice

This repository is open source and accepts public contributions. All code, issues and pull requests are publicly visible. see the LICENSE file for details. Software is provided “as is,” without warranty of any kind, and no security or compliance guarantees are implied. You are responsible for evaluating fitness for your use case and for securing your own deployments and data.

- Do not include secrets, personal data, or confidential information in code, issues, PRs, logs, or example payloads. 

## Privacy and Compliance

RailTracks does not itself provide compliance guarantees. Deployers are responsible for meeting regulatory obligations, including data minimization, retention, and residency. If you forward logs or store execution data, ensure your usage aligns with applicable laws and your provider agreements.

## Safe-by-Practice Checklist

- Only install and run trusted tools/plugins; review source and supply chain.
- Treat all LLM inputs/outputs as untrusted; validate/verify before acting.
- Restrict tool capabilities and credentials to the minimum needed.
- Control data persistence: protect `.railtracks`, avoid storing secrets or sensitive data unless required, and clean up after debugging.
- Keep logs minimal in production and scrub sensitive values if logging is enabled.
- Enforce network and filesystem boundaries at the environment level (containers/VMs, proxies, firewalls).
- Pin dependencies where feasible and follow your organization’s security scanning practices.

## Contact

- Security contact: [Security Email](mailto:security.railtracks@railtown.ai)
- Please include "[RailTracks Security]" in the subject line.
- If you require an encrypted channel, please indicate so in your initial email. We can coordinate an alternative secure method of communication.

## Changes to This Policy

This document may be updated as the project evolves. Material changes will be noted in release notes.
