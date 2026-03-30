# OpenAI alignment notes

This repository is shaped to feel closer to something OpenAI would plausibly ship for a local Codex desktop operator.

## Product choices

- plugin-first packaging rather than an unsupported custom extension point
- one bundled skill that teaches Codex how to use the helper
- one local helper with deterministic JSON output
- explicit approval boundaries for riskier actions
- installation flows for personal and repo marketplaces

## Behavior choices

- inspect state before acting
- prefer one action per step
- verify changes before reporting success
- do not hide risk behind autonomous execution
- keep logs useful without storing typed secrets

## Tradeoffs kept visible

This version is honest about what still needs a real Mac.
It does not pretend to solve semantic UI targeting or privacy redaction yet.
Those are good next steps, but they should come after the base control plane is reliable.
