# Docker Architecture for AuraNexus

Multi-agent DND party simulation with containerized characters.

## Architecture

```
┌──────────────────────────── auranexus-network ────────────────────────────┐
│                                                                            │
│  Ollama :11434 ──┐                                                        │
│  KoboldCPP :5001 ┼──→ Core-App :8000 ──→ agent-fighter, agent-wizard,   │
│                  │                         agent-cleric, agent-dm         │
│  (Shared LLMs)   │         (Orchestrator)  (Individual characters)        │
└────────────────────────────────────────────────────────────────────────────┘
```

## Services

### LLM Backends
- **ollama** (:11434): GPU-enabled, shared models
- **koboldcpp** (:5001): GGUF alternative backend

### Core Application (:8000)
- Agent coordination & handoffs
- Shared memory/RAG
- Optional Gradio UI (:7860)

### Agent Containers
Each runs [Dockerfile.agent](../Dockerfile.agent) with unique config:
- **agent-fighter**: Warrior (`data/characters/fighter.yaml`)
- **agent-wizard**: Spellcaster (`data/characters/wizard.yaml`)
- **agent-cleric**: Healer (`data/characters/cleric.yaml`)
- **agent-dm**: Dungeon Master (`data/characters/dungeon_master.yaml`)

## Container DNS

| Service | Container | Internal URL |
|---------|-----------|--------------|
| ollama | auranexus-ollama | http://ollama:11434 |
| core-app | auranexus-core | http://core-app:8000 |
| agent-fighter | auranexus-agent-fighter | http://agent-fighter:8000 |

## File Structure

```
AuraNexus/
├── docker-compose.yml
├── Dockerfile              # Core app
├── Dockerfile.agent        # Agent runtime
├── data/
│   ├── characters/         # Agent YAML configs
│   ├── shared/             # Shared campaign state
│   └── campaign/           # DM-specific data
└── src/
    ├── agent_runtime.py    # Agent entrypoint
    └── ollama_client.py
```


## Quick Start

```bash
# Start all services
docker-compose up -d

# Start LLM backends + core only
docker-compose up -d ollama koboldcpp core-app

# View logs
docker-compose logs -f agent-wizard

# Stop all
docker-compose down
```

## Agent Communication Example

```python
# agent_runtime.py
class AgentCharacter:
    def __init__(self, config_path: str):
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.core_app_url = os.getenv("CORE_APP_URL", "http://core-app:8000")
        self.ollama_client = OllamaClient(host=self.ollama_url)
    
    def chat(self, user_message: str) -> str:
        response = self.ollama_client.chat(
            model=self.config['model'],
            messages=[{"role": "user", "content": user_message}]
        )
        return response['message']['content']
```

## Benefits

✅ **Isolation**: Each agent is independent  
✅ **Scalability**: Add/remove agents dynamically  
✅ **Fault Tolerance**: One agent crash doesn't affect others  
✅ **Shared Resources**: All use same LLM backends (no model duplication)  
✅ **Easy Testing**: Test agents individually

## Integration with cagent Patterns

Implements patterns from `docker/cagent`:
- Multi-agent teams (Section 15.1)
- YAML configurations (15.2)
- Agent handoffs (15.4)
- Per-agent toolsets (15.3)

**Difference**: cagent is monolithic (all agents in one process), this is distributed (agents in separate containers).
    - AGENT_NAME=rogue
    - OLLAMA_BASE_URL=http://ollama:11434
    - CORE_APP_URL=http://core-app:8000
  networks:
    - auranexus-network
```

### Multiple LLM Backends

Run different models for different characters:

```yaml
agent-wizard:
  environment:
    - PREFERRED_MODEL=llama3.2:70b  # Powerful model for wizard
    - OLLAMA_BASE_URL=http://ollama:11434

agent-fighter:
  environment:
    - PREFERRED_MODEL=llama3.2:7b   # Faster model for fighter
    - OLLAMA_BASE_URL=http://ollama:11434
```

## Benefits of This Architecture

1. **Isolation**: Each agent is a separate process with its own resources
2. **Scalability**: Add/remove agents without restarting others
3. **Fault Tolerance**: If wizard crashes, fighter keeps working
4. **Resource Control**: Set CPU/memory limits per agent
5. **Shared Backend**: All agents use same LLM models (no duplication)
6. **Easy Development**: Test individual agents independently
7. **Multi-Platform**: Works on Windows, Linux, Mac with Docker

## Next Steps

1. **Implement `agent_runtime.py`**: Agent container entrypoint
2. **Design Agent API**: Core app endpoints for agent coordination
3. **Create Character YAMLs**: Define personalities in `data/characters/`
4. **Handoff Protocol**: How agents transfer control
5. **Shared Memory**: Campaign state storage in `data/shared/`
6. **Test Suite**: Integration tests for multi-agent scenarios

## Integration with cagent Patterns (Section 15)

This architecture directly implements patterns from `docker/cagent`:

- **Multi-agent teams** (15.1): Each agent container = sub-agent
- **YAML configs** (15.2): Character definitions in `data/characters/`
- **Agent handoffs** (15.4): Core app coordinates handoff protocol
- **Per-agent tools** (15.3): Each agent can have unique MCP toolsets
- **Sub-agent delegation** (15.7): Core app delegates to specialists

The key difference: cagent is monolithic (all agents in one process), this is distributed (agents in separate containers).
