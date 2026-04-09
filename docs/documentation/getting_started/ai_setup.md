# AI Coding Assistant Setup

Railtracks ships with built-in support for the most popular AI coding assistants. Running one command installs a **skill**: a structured knowledge file that teaches your assistant how to build agents, use tools, and compose workflows correctly.

Without a skill, your assistant has to guess at the API. With one, it knows exactly what `rt.agent_node()`, `rt.function_node()`, and `rt.Flow` expect; and it won't make things up.

## Installation

Make sure the CLI is installed first:

```bash
pip install 'railtracks[cli]'
```


## Supported Assistants

=== "Claude Code"

    Installs a skill file at `.claude/skills/agent-builder/SKILL.md`. Claude Code automatically picks up skills in this directory and applies them when you ask it to build an agent.

    ```bash
    railtracks add claude:agent-builder
    ```

    ??? success "What gets created"
        ```
        .claude/
        └── skills/
            └── agent-builder/
                └── SKILL.md   ← railtracks agent-building knowledge
        ```

=== "GitHub Copilot"

    Appends the skill to `.github/copilot-instructions.md`, which Copilot reads as workspace-level instructions in every chat.

    ```bash
    railtracks add copilot:agent-builder
    ```

    ??? success "What gets created / updated"
        ```
        .github/
        └── copilot-instructions.md   ← skill appended inside marker comments
        ```

    !!! note "Idempotent"
        Running this command twice is safe — it detects the existing section and skips it. Use `--force` to replace it.

=== "Cursor"

    Installs a `.mdc` rules file at `.cursor/rules/agent-builder.mdc`. Cursor loads these rules when they match the current context.

    ```bash
    railtracks add cursor:agent-builder
    ```

    ??? success "What gets created"
        ```
        .cursor/
        └── rules/
            └── agent-builder.mdc   ← railtracks agent-building knowledge
        ```

## Options

| Flag | Description |
|---|---|
| `--force` | Overwrite an existing skill without prompting |

```bash
railtracks add --force claude:agent-builder
```

## Available Skills

| Skill | Description |
|---|---|
| `agent-builder` | Build agents, tools, flows, and multi-agent workflows with railtracks |


## How It Works

Skills are bundled **inside the railtracks package**, no internet connection required. When you run `railtracks add`, the CLI:

1. Reads the bundled skill content for the requested skill
2. Formats it with the frontmatter and structure that your specific assistant expects
3. Writes it to the correct location in your project

!!! tip "Commit the files"
    These files are small and stable. Committing them means every developer on your team gets the same assistant behaviour out of the box, no manual setup required.

!!! warning "Existing files"
    For Claude Code and Cursor, if the target file already exists you'll be prompted to confirm before overwriting. Pass `--force` to skip the prompt.

## Example: Building Your First Agent

Once the skill is installed, just ask your assistant:

```
Build me a railtracks agent that searches the web and summarises results
```

Your assistant will use the skill to generate correct `rt.function_node` tools, a properly configured `rt.agent_node`, and a `rt.Flow` with a runnable `__main__` block without you having to paste docs into the chat.
