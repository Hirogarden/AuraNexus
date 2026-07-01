# AuraNexus

AuraNexus is a local-first AI runtime with strict sandbox boundaries, in-process llama.cpp inference, split companion and storyteller mode pipelines, and persistent session/state storage rooted under a single sandbox workspace.

## Launcher

The launcher entry point is [launcher.py](launcher.py). Use the project virtual environment first.


```

### Companion One-Shot

```bash
python launcher.py \
  --model-path /absolute/path/to/model.gguf \
  --allow-command python3 \
  companion \
  --message "I feel uncertain today."

# CPU fast profile for lighter local turnaround
python launcher.py \
  --model-path /absolute/path/to/model.gguf \
  --allow-command python3 \
  --cpu-fast \
  companion \
  --message "Quick check-in"
```

### Companion Interactive Session

```bash
python launcher.py \
  --model-path /absolute/path/to/model.gguf \
  --allow-command python3 \
  companion \
  --session-name "Primary"
```

### Storyteller One-Shot New Story

```bash
python launcher.py \
  --model-path /absolute/path/to/model.gguf \
  --allow-command python3 \
  story \
  --title "Pass of Cinders" \
  --genre "Fantasy" \
  --tone "Tense" \
  --setting "A volcanic borderland under ashfall." \
  --player-name "Mira" \
  --message "I approach the shrine."
```

### Storyteller Resume Existing Session

```bash
python launcher.py \
  --model-path /absolute/path/to/model.gguf \
  --allow-command python3 \
  story \
  --session-id story_20260630_120000

### GPU Offload Tuning

```bash
python launcher.py \
  --model-path /absolute/path/to/model.gguf \
  --allow-command python3 \
  --gpu-layers 20 \
  --ctx-size 8192 \
  companion \
  --message "hello"
```

Use `--gpu-layers 0` for CPU-only. Use `--gpu-layers -1` to attempt full model offload when your llama.cpp build supports your GPU backend.
```

### List Saved Sessions

```bash
python launcher.py --model-path /absolute/path/to/model.gguf --allow-command python3 list-chat-sessions
python launcher.py --model-path /absolute/path/to/model.gguf --allow-command python3 list-story-sessions
```

### Readiness Check (No Model Load Required)

```bash
python launcher.py --no-isolation --allow-command python3 doctor
```

The doctor command verifies sandbox state files, registered tools, command allowlist status, model path presence, and machine capabilities.
It now reports:

- detected CPU and RAM profile
- detected NVIDIA GPUs (when `nvidia-smi` is available)
- whether installed `llama-cpp-python` supports GPU offload
- recommended launch profile (`cpu-fast` or GPU-oriented)

This allows AuraNexus installs on different machines to self-check hardware readiness instead of relying on manual per-device assumptions.

### Install and Run Demo Skill (No Model Load Required)

```bash
python launcher.py --no-isolation --allow-command python3 install-demo-skill
python launcher.py --no-isolation --allow-command python3 run-demo-skill --text "hello from sandbox"
```

The demo skill validates OpenClaw schema loading, tool registration, payload handoff, and sandboxed command execution.

## Sandbox State Layout

AuraNexus persists all runtime state inside the configured sandbox workspace:

- `state/bootstrap.json`: versioned bootstrap manifest and deterministic seed payload
- `state/world_state.json`: absolute fact store
- `state/lorebook.json`: persisted lore cards and active persona state
- `sessions/companion/`: companion session files
- `sessions/story/`: storyteller session files
- `skills/`: OpenClaw skill schemas

## First-Run Seeding

On first run in a fresh sandbox, AuraNexus seeds:

- permanent system world facts for `aura.name`, `user.name`, and the sandbox privacy boundary
- a companion lore card for reassurance-oriented dialogue cues
- a storyteller lore card for continuity and sensory detail cues

Seeding only applies when the target sandbox has no existing world facts or lore cards.