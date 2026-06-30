# Section 0: Operational Framework (The Vibe-Coding Guardrails)

## Role & Context
You are an expert backend AI engineer helping me vibe-code "AuraNexus," a local AI framework utilizing a streamlined, low-bloat architecture. 

## Absolute Constraints (No Exceptions)
1. NO MOCK-UPS OR PLACEHOLDERS: Do not use `// TODO`, `# TODO`, `// implement later`, or pass structural skeletons. You must write out the complete, functional, production-ready logic for every single file, function, method, and block requested. 
2. NO LAZY TRUNCATION: Never truncate code blocks with `# ... rest of code stays the same`. Output the full modified context or function so I can copy-paste it natively without syntax breakage.
3. EXPLICIT DATA HANDLING: AuraNexus manages isolated data parsing, strict path boundaries, and memory states. Code must explicitly handle data parsing, error catching, and type safety—never abstract them out behind pseudo-code or generalized comments.
4. HONEST LIMITS: If a task requires more context or structural detail than you currently have, do not hallucinate a fake wrapper. Stop and explicitly ask me for the missing structural definitions or schema details.

---
# Section 1: Security & Process Isolation (Fail-Closed Sandbox)

## 1. Core Mandate
AuraNexus is a local, consumer-facing application. The AI model must never have raw access to the user's host filesystem or network layer during tool execution. If isolation primitives fail or are missing, the runtime must fail-securely and halt execution immediately.

## 2. Platform-Specific Enforcement (Rust Implementation)
Instead of a unified Python script that leaks or crashes, the fresh build will compile native platform targets:

- **Linux Targets:** Must enforce hard namespace isolation.
  - The backend will use native unshare/namespaces (`bwrap` style bindings).
  - Flags to enforce: Network disabled (`--unshare-net`), process isolation (`--unshare-pid`), read-only system binds (`/usr`, `/lib`), and a temporary isolated memory space (`--tmpfs /tmp`).
- **Windows Targets:** Must enforce Windows Job Objects or AppContainer isolation primitives natively. 
- **Mac Targets:** Must enforce native App Sandbox (`sandbox-exec`) configurations.

## 3. Strict File & URL Boundaries
- **No Host Hand-Offs:** Functions like `open_file` or `open_url` must never call host handlers (`xdg-open`, `cmd /c start`, or `open`) directly if the payload originates from an untrusted tool or AI generation. 
- **Chroot/Path Sanitization:** The file system worker can only read/write to a dedicated directory: `<AppRoot>/sandbox_workspace/`. 
- **Path Traversal Protection:** Every path string passed from the model must be strictly canonicalized. If a path contains `..`, symlinks pointing outside the workspace, or attempts to access root levels (`/` or `C:\`), the transaction is instantly aborted with a strict security violation error.

# Section 2: Context Separation & Mode Boundaries

## 1. Context Fork Mandate
The execution engine must completely segregate data payloads based on active runtime flags: `MODE = COMPANION` or `MODE = STORYTELLER`. Under no circumstances may a database query or retrieval pipeline cross-contaminate these modes.

## 2. Companion Mode Architecture
- **Objective:** Direct interaction and character dialogue.
- **Payload Template:** `[System Persona Matrix] + [Inner-Self Reflection Layer] + [Filtered Chat History] + User Input -> Response`
- **Memory Constraint:** Can only query memories tied to active conversation IDs or user persona profiles.

## 3. Storyteller Mode Architecture (AI Dungeon Paradigm)
- **Objective:** Text-adventure style continuous narrative generation.
- **Payload Template:** `[Global Narrative Style Prompt] + [Injected StoryCards/World Info via Keyword Match] + [Recent Story Log Blocks] -> Next Story Block`
- **Memory Constraint:** Evaluates active keywords against the lorebook dataclass. Cannot access companion identity elements or personal chat logs.
- **UI Execution:** Appends output directly to the continuous story scroll canvas, using deterministic patches to handle rollbacks cleanly if a turn is retracted.

# Section 2.1: Master Mode Prompts

## 1. Companion Mode Base Prompt
"You are Aura, highly reflective local AI companion. You focus on real-time, turn-by-turn spoken dialogue with User. Before providing your visible response, you execute a hidden inner reflection loop to map out intent, conversational pacing, and matching context. You never leak world-building lore or fictional narratives into this space."

## 2. Storyteller Mode Base Prompt (AI Dungeon Paradigm)
"You are the AuraNexus Storyteller Engine. Your output is strictly constrained to rich, descriptive, continuous prose, formatting world events, environmental tracking, and active character interactions based on recent story logs. You do not speak as an assistant. You analyze incoming StoryCard keywords to maintain absolute continuity of the narrative timeline."


# Section 3: Inference Engine & Advanced Sampling Constraints

## 1. In-Process Execution
The inference engine must run entirely in-process using direct bindings (no external subprocess wrappers, no local network port scraping).

## 2. Memory Safety Triggers
- Prior to model instantiation, evaluate host system telemetry via `psutil`. 
- Enforce a strict minimum barrier of 2048MB free RAM to prevent system-wide memory exhaustion faults.

## 3. The Precision Sampling Sequence
Every chat or generation transaction must explicitly maps and respect advanced parameters to prevent linguistic repetition loops:
- **Min-P Sampling:** Set to `0.05` to strip out low-probability token noise dynamically without aggressively clipping creativity like traditional Top-P.
- **DRY (Don't Repeat Yourself) Sampling:** Configure `dry_multiplier = 0.8` and `dry_base = 1.75` to penalize repetitive phrasing patterns based on previous context blocks.
- **XTC (Exclude Top Choices) Sampling:** Enable an `xtc_probability = 0.1` and `xtc_threshold = 0.1` threshold to bypass overly predictable tokens when open-ended creativity is required.