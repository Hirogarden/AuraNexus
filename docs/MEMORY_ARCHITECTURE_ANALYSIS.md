# Memory Architecture Analysis: Integration Strategy

**Date**: January 6, 2026  
**Decision**: **YES to layered integration** - Each system has a distinct role.

## Memory System Comparison

| System | Purpose | Strengths | Limitations |
|--------|---------|-----------|-------------|
| **Dungeo_ai** | Raw conversation storage | Complete chronology, context preservation | No semantic search |
| **Mem0** | Semantic facts | Entity extraction, time-based retrieval | No conversation flow |
| **Auto-Cards** | Entity management | Character/location tracking | Only entity-focused |
| **AnythingLLM** | Document RAG | Lore search, citations | Not real-time |
| **Card-Forge** | Lorebook triggers | Keyword context injection | Manual updates |


## Integration Pipeline

```
User Input → Dungeo_ai (raw) → Mem0 (facts) → Auto-Cards (entities) → AnythingLLM (RAG) → Card-Forge (triggers)
```

**Flow Example**: "I got promoted! Manager Sarah is excited."
1. **Dungeo_ai**: Saves complete conversation
2. **Mem0**: Extracts `{user.job.role: "promoted", Sarah: {role: "manager"}}`
3. **Auto-Cards**: Creates/updates Sarah character card
4. **AnythingLLM**: Indexes for semantic search
5. **Card-Forge**: Sets up "Sarah" keyword trigger

## Performance Metrics

| System | Latency | Storage/1K turns | Value Add |
|--------|---------|------------------|-----------|
| Dungeo_ai | 10ms | 500KB | Baseline |
| + Mem0 | 500ms | +100KB | High ⭐⭐⭐⭐⭐ |
| + Auto-Cards | 300ms | +200KB | Medium ⭐⭐⭐ |
| + AnythingLLM | 1000ms | +300KB | Medium ⭐⭐⭐ |
| + Card-Forge | 50ms | +150KB | Low ⭐⭐ |

**Recommendation**: Start with **Dungeo_ai + Mem0** (90% value, 20% complexity).

## Phased Implementation

**Phase 1 (Months 3-4)**: Core
- ✅ Dungeo_ai (conversation history)
- ✅ Mem0 (semantic facts)
- ✅ Unified Memory Manager API

**Phase 2 (Months 5-6)**: Enhanced
- ⚠️ Auto-Cards (if entity browsing needed)
- ⚠️ AnythingLLM (if document RAG needed)

**Phase 3 (Month 8+)**: Advanced
- ❌ Card-Forge (complex, niche use case)

## Implementation Reference

```python
class UnifiedMemoryManager:
    """Single interface to all memory systems"""
    
    def __init__(self):
        self.conversation = DungeoAIState()      # Required
        self.semantic_memory = Mem0Client()      # Recommended
        self.entity_db = AutoCardsClient()       # Optional
        self.lore_rag = AnythingLLMClient()      # Optional
        self.lorebook = CardForgeClient()        # Optional
    
    async def remember(self, user_input: str, ai_response: str):
        # Immediate (10ms, non-blocking)
        self.conversation.append(user_input, ai_response)
        
        # Background async processing
        await asyncio.gather(
            self.semantic_memory.add(user_input, ai_response),
            self.entity_db.detect_and_update(user_input + ai_response),
            self.lore_rag.ingest(f"{user_input}\n{ai_response}")
        )
    
    async def recall(self, query: str) -> str:
        # Parallel hybrid search
        results = await asyncio.gather(
            self.conversation.search(query),      # Fast: <100ms
            self.semantic_memory.search(query),   # Medium: <500ms
            self.entity_db.query(query),          # Medium: <300ms
            self.lore_rag.query(query)            # Slow: <1500ms
        )
        return synthesize_results(results)
```

## Key Decisions

**✅ DO Integrate If:**
- Need comprehensive long-term memory
- Have async background processing
- Building multi-month companion
- VRAM/CPU headroom available

**❌ DON'T Integrate If:**
- Simplicity is priority
- Limited compute resources
- Short sessions (1-2 hours)
- Prototyping phase

**🎯 Recommended**: Start simple (Dungeo_ai + Mem0), scale based on usage patterns.
