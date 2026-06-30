# Seed Docs Packet for Fresh Workspace

Date: 2026-06-30
Purpose: condensed input set for reconstructing AuraNexus without reintroducing scope drift.

## Core Contract Docs

1. docs/V1_ARCHITECTURE_CONTRACT.md
- Why: defines single-source subsystem ownership and explicit exclusions.

2. README.md
- Why: concise runtime shape for the current AuraNexus desktop target.

3. CURRENT_STATUS.md
- Why: practical truth table of what is implemented vs deferred.

4. docs/SECURITY_ARCHITECTURE.md
- Why: fail-closed and sandbox model that must survive refactor.

## Runtime Reference Docs

5. START_HERE.md
- Why: onboarding and operation baseline for contributors.

6. PROJECT_STRUCTURE.md
- Why: practical map of runtime-relevant layout.

7. ROADMAP.md
- Why: stage boundaries and sequencing context.

## External Reference Docs (Pattern-Only)

8. ../the-nexus-core/README.md
- Why: retrieval/indexing and citation quality feature map.

9. ../the-nexus-core/BRAIN_LIKE_AI.md
- Why: advanced subsystems for future selective adoption.

10. ../Daniel-Sweet-Suite/Daniel-Sweet-Suite/README.md
- Why: OpenClaw-style workflow/config pattern reference.

## Rules for Using This Packet

- Use these files to define architecture decisions, not to justify adding every available feature.
- If two files imply different owners for the same subsystem, V1_ARCHITECTURE_CONTRACT.md wins.
- Any new capability proposal must state: owner, boundary, and why it does not add a second parallel subsystem.
