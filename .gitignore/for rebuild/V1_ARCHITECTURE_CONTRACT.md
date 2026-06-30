# AuraNexus V1 Architecture Contract

Date: 2026-06-30
Status: active contract for rebuild

## Purpose

Define the single-source ownership model for the fresh AuraNexus rebuild so one subsystem is implemented once, not three times.

## V1 Product Boundary

In scope:
- Desktop-first local application
- Local LLM support
- Long-term memory and RAG retrieval
- Character/story mode
- Sandboxed tool/action execution
- Plugin-style tool extensions
- External ingest and optional web retrieval

Out of scope for V1:
- Voice (STT/TTS)
- Avatar/VRM/VTuber stack
- Image generation stack
- Cloud-first provider requirements
- Experimental Rust rewrite specifications

## Canonical Ownership

Each subsystem has one owner. If another implementation exists, it is reference-only unless promoted by explicit decision.

1. Desktop shell and session UX
- Owner: auranexus/ui from AuraNexus.old
- Contract: all user interaction flows through the desktop shell first

2. Orchestration and turn pipeline
- Owner: auranexus/core.py from AuraNexus.old
- Contract: prompt assembly and turn lifecycle stay centralized

3. Security gate and sandbox boundary
- Owner: security/gate.py and security/sandbox.py from AuraNexus.old
- Contract: fail-closed startup and out-of-process action execution remain mandatory

4. Story runtime and persona/world context
- Owner: auranexus/story/session.py and auranexus/story/lorebook.py from AuraNexus.old
- Contract: story mode is first-class, not a plugin

5. Retrieval/indexing quality features
- Owner: selected concepts from the-nexus-core (engine/indexing/enhancements)
- Contract: import proven retrieval/citation/rerank patterns without replacing desktop-first architecture

6. Memory pipeline
- Owner: HiRAG-first path from AuraNexus.old for V1
- Contract: one active memory pipeline at runtime
- Note: layered_memory_system from the-nexus-core is reference-only unless migration is approved

7. Provider abstraction
- Owner: auranexus/engine/provider.py family from AuraNexus.old
- Contract: local provider path must work without cloud keys

8. Tool schema and action dispatch
- Owner: auranexus/actions/schema_registry.py and auranexus/actions/executor.py
- Contract: schema-first tool calls, one action per model response, sandboxed execution

9. Plugin extension model
- Owner: auranexus/actions extension worker path
- Contract: extension code never executes in-process

10. Ingest and external knowledge flow
- Owner: NexusDocStore and associated AuraNexus knowledge panel path
- Contract: ingest is explicit, inspectable, and section-scoped

## Non-Goals

- No merge-all strategy across AuraNexus.old, the-nexus-core, Miniverse, and external ecosystem repos.
- No parallel memory systems in production path.
- No second orchestration core running beside AuraNexusCore.

## Phase Order

Phase A: Core contracts and security invariants
- Keep fail-closed startup
- Keep sandbox-required action execution
- Finalize subsystem ownership table

Phase B: Retrieval and memory stabilization
- Keep HiRAG as sole active memory runtime
- Port targeted retrieval quality improvements from the-nexus-core
- Add consistency tests for citations and retrieval provenance

Phase C: Tool registry and plugin hardening
- Keep schema-driven tool calls
- Keep one-tool-call-per-response invariant
- Add registry consistency checks and extension ownership diagnostics

Phase D: Story runtime and UX consolidation
- Preserve story session controls
- Preserve world/lore editing loops
- Align retrieval context boundaries between companion and story modes

## Completion Criteria for V1

- App runs desktop-first with local provider defaults
- One memory pipeline active at runtime
- Tool execution remains sandboxed and auditable
- Story mode works without enabling out-of-scope features
- All out-of-scope systems remain excluded by default
