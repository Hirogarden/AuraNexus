# Quick Reference: RLM Integration for AuraNexus

**Purpose**: Quick-start guide for implementing MIT's Recursive Language Models in AuraNexus  
**Full Guide**: See `RLM_INTEGRATION_GUIDE.md` for complete details

---

## 🚀 TL;DR - What is RLM?

**MIT's Recursive Language Models** (Dec 2025) enable LLMs to handle contexts **100x longer** by:
- Breaking context into chunks
- Recursively processing each chunk
- Synthesizing results intelligently
- Avoiding "context rot" (quality degradation over long contexts)

**Paper**: https://arxiv.org/pdf/2512.24601

---

## 🎯 Why AuraNexus Needs This

Our **5-layer hierarchical memory** already handles long conversations well, but RLM makes it **dramatically better**:

| Without RLM | With RLM |
|-------------|----------|
| Struggle with 500+ messages | Handle 10,000+ messages easily |
| Simple summaries lose nuance | Multi-level compression preserves details |
| Can't synthesize cross-session | Find patterns across all sessions |
| Context limit bottleneck | No practical limit |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│ USER QUERY: "Summarize all dragon encounters"      │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STEP 1: Retrieve from Memory Layers                │
│ → Result: 247 messages about dragons               │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STEP 2: RLM Decision                                │
│ → 247 messages > 50 threshold → USE RLM             │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STEP 3: Chunk Messages                              │
│ → Chunk 1: msgs 1-20 (semantic group)              │
│ → Chunk 2: msgs 21-40 (semantic group)             │
│ → ... (12 chunks total)                             │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STEP 4: Recursive Processing (Parallel)             │
│ ┌────────────────┐ ┌────────────────┐               │
│ │ Chunk 1 → LLM  │ │ Chunk 2 → LLM  │ ...           │
│ │ "Red dragon    │ │ "Gold dragon   │               │
│ │  in cave"      │ │  in mountains" │               │
│ └────────────────┘ └────────────────┘               │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ STEP 5: Synthesize Results                          │
│ → Combine chunk summaries                           │
│ → Create coherent narrative                         │
│ → Add citations (msg IDs)                           │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│ RESPONSE:                                           │
│ "You've had 3 major dragon encounters:              │
│  1. Red dragon in cave (msg #45)                    │
│  2. Gold dragon in mountains (msg #123)             │
│  3. Ancient dragon at tower (msg #201)"             │
└─────────────────────────────────────────────────────┘
```

---

## 📂 Files to Create

```
src/rlm/
├── __init__.py
├── rlm_manager.py           # Core: Recursive processing engine
├── rlm_compressor.py        # Compression: Multi-level summaries
├── rlm_retriever.py         # Retrieval: Smart synthesis
├── rlm_query_planner.py     # Planning: Query strategy
└── cross_session_rlm.py     # Advanced: Cross-session ops
```

---

## 🔧 Integration Points

### 1. Memory Query Enhancement
**File**: `src/hierarchical_memory.py`

```python
def query_memory(self, query: str, use_rlm: bool = True):
    messages = self._retrieve_from_layers(query)
    
    # NEW: RLM processing for large contexts
    if use_rlm and len(messages) > 50:
        return self.rlm_manager.recursive_process(messages, query)
    
    return self._format_messages(messages)
```

### 2. Background Compression
**File**: `src/hierarchical_memory.py`

```python
async def _compress_to_medium_term(self, messages):
    # OLD: Simple summary
    # summary = self._simple_summarize(messages)
    
    # NEW: RLM multi-level compression
    compressed = self.rlm_compressor.compress_conversation_segment(
        messages, recursion_level=2
    )
    return compressed
```

### 3. Cross-Session Queries
**File**: `src/hierarchical_memory.py` (SessionManager)

```python
def query_all_sessions(self, query: str, use_rlm: bool = True):
    sessions = self._get_all_sessions()
    
    # NEW: Cross-session RLM synthesis
    if use_rlm:
        return self.cross_session_rlm.query_across_sessions(
            query, [s.id for s in sessions]
        )
```

---

## 🎬 Implementation Phases

### Phase 1: Core RLM (Week 1) - **START HERE**
- [ ] Create `src/rlm/rlm_manager.py`
- [ ] Implement basic chunking (20 msgs per chunk)
- [ ] Implement recursive processing (max 3 levels)
- [ ] Integrate with `query_memory()`
- [ ] Test with 100+ message conversation

**Deliverable**: Basic RLM works for large queries

### Phase 2: Compression (Week 2)
- [ ] Create `src/rlm/rlm_compressor.py`
- [ ] Multi-level summaries (brief/medium/detailed)
- [ ] Entity extraction (characters, items, places)
- [ ] Integrate with background compression
- [ ] Test compression quality

**Deliverable**: Better long-term memory compression

### Phase 3: Smart Retrieval (Week 3)
- [ ] Create query planner and retriever
- [ ] Automatic RLM decision logic
- [ ] Citation support (link to message IDs)
- [ ] Test with complex queries

**Deliverable**: Intelligent retrieval with citations

### Phase 4: Cross-Session (Week 4)
- [ ] Create `cross_session_rlm.py`
- [ ] Query across multiple sessions
- [ ] Entity aggregation across sessions
- [ ] Test with multiple storytelling sessions

**Deliverable**: Find patterns across all sessions

### Phase 5: Polish (Week 5)
- [ ] Add UI toggle for RLM
- [ ] Performance optimization
- [ ] Comprehensive testing
- [ ] Documentation

**Deliverable**: Production-ready RLM integration

---

## 🧪 How to Test

### Test 1: Basic RLM Processing
```python
# Create session with 100 messages
memory = get_session("test_story")
for i in range(100):
    memory.add_message("user", f"Message {i}")

# Query with RLM
result = memory.query_memory("Summarize everything", use_rlm=True)

# Verify
assert result.method == "rlm_recursive"
assert len(result.answer) > 0
print(result.answer)  # Should be coherent summary
```

### Test 2: RLM Compression
```python
# Trigger background compression
await asyncio.sleep(5)  # Wait for idle

# Check compression stats
stats = memory.get_stats()
assert stats["compressed_segments"] > 0
assert stats["multi_level_summaries"] == True
```

### Test 3: Cross-Session Query
```python
# Create 3 sessions with different stories
session1 = create_session("fantasy_1", ...)
session2 = create_session("fantasy_2", ...)
session3 = create_session("fantasy_3", ...)

# Add wizard characters to each
# ...

# Cross-session query
manager = get_session_manager()
result = manager.query_all_sessions(
    "What are all my wizard characters?",
    use_rlm=True
)

# Verify finds wizards from all 3 sessions
assert len(result.entities) >= 3
```

---

## ⚠️ Important Gotchas

### 1. **Token Costs**
RLM makes multiple LLM calls (one per chunk + synthesis)

**Solution**: Use cheaper model for chunks, expensive for synthesis
```python
RLM_CONFIG = {
    "chunk_model": "gpt-3.5-turbo",    # Fast & cheap
    "synthesis_model": "gpt-4",         # Quality
}
```

### 2. **Recursion Limits**
Prevent infinite recursion

**Solution**: Hard limit at 3 levels
```python
MAX_RECURSION_DEPTH = 3
```

### 3. **Chunk Boundaries**
Important info might span chunks

**Solution**: Overlap chunks by 2-3 messages
```python
chunk_size = 20
overlap = 3
```

### 4. **Encryption**
RLM must work with encrypted medical data

**Solution**: RLM operates after decryption (in memory)
```python
# Decrypt → RLM process → Results (not re-encrypted)
```

### 5. **Performance**
Recursive processing can be slow

**Solutions**:
- Process chunks in parallel (`asyncio.gather()`)
- Cache intermediate results
- Stream results progressively
```python
async def parallel_process(chunks):
    tasks = [process_chunk(c) for c in chunks]
    return await asyncio.gather(*tasks)
```

---

## 🎓 Key Concepts

### Recursive Processing
```
Question: "Summarize 500 messages"

Standard Approach (Fails):
All 500 messages → LLM (context overflow or context rot)

RLM Approach (Works):
500 messages → Split into 25 chunks of 20
├─ Chunk 1 → LLM: "Summarize these 20 messages"
├─ Chunk 2 → LLM: "Summarize these 20 messages"
├─ ... (25 times)
└─ 25 summaries → LLM: "Synthesize these summaries"
   └─ Final coherent summary
```

### Semantic Chunking
```
Bad Chunking (Arbitrary):
Messages 1-20, 21-40, 41-60
→ Might split a conversation mid-topic

Good Chunking (Semantic):
Group by topic/entity:
- Chunk 1: Dragon encounter (msgs 1-15)
- Chunk 2: Village visit (msgs 16-35)
- Chunk 3: Character development (msgs 36-50)
```

### Multi-Level Summaries
```
Original: 200 messages

Level 3 (Brief):
"A dragon quest adventure with 3 major battles"

Level 2 (Medium):
"The party encountered a red dragon in a cave, fought through 
mountain passes, and defeated an ancient dragon at a tower..."

Level 1 (Detailed):
"[Paragraph 1: Cave encounter details]
[Paragraph 2: Mountain journey]
[Paragraph 3: Tower battle]
[Paragraph 4: Character development]"
```

---

## 📊 Success Metrics

| Metric | Target |
|--------|--------|
| Max context size | 1000+ messages (from ~100) |
| Query quality | 8+/10 coherence score |
| Compression ratio | 0.2-0.3 (preserve 70-80% info) |
| Processing time | < 5 seconds for 500 messages |
| Citations accuracy | 95%+ correct message IDs |

---

## 🚦 Getting Started Checklist

**Before you start**:
- [ ] Read full guide: `RLM_INTEGRATION_GUIDE.md`
- [ ] Read MIT paper: https://arxiv.org/pdf/2512.24601
- [ ] Understand current memory system: `HIERARCHICAL_MEMORY_GUIDE.md`
- [ ] Set up test environment with 100+ message session

**Week 1 Goals**:
- [ ] Create RLM directory structure
- [ ] Implement basic `RLMContextManager`
- [ ] Add simple chunking (20 msgs, no overlap)
- [ ] Add basic recursive processing (1 level only)
- [ ] Integrate with one query function
- [ ] Test with 100-message conversation
- [ ] Verify coherent summary output

**Validation**:
```bash
# Run this test to verify Week 1 is complete
python test_rlm_basic.py

# Expected output:
# ✅ RLM Manager initialized
# ✅ Chunking works (5 chunks from 100 messages)
# ✅ Recursive processing works
# ✅ Synthesis coherent
# ✅ Integration with query_memory works
```

---

## 🔗 API Examples

### Enable RLM for Query
```bash
curl -X POST http://localhost:8000/memory/query \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "fantasy_story_01",
    "query": "Summarize all dragon encounters",
    "use_rlm": true
  }'
```

### Response
```json
{
  "answer": "You've had 3 major dragon encounters...",
  "method": "rlm_recursive",
  "citations": [
    {"msg_id": "msg_45", "excerpt": "attacked the red dragon"},
    {"msg_id": "msg_123", "excerpt": "gold dragon in mountains"}
  ],
  "metadata": {
    "chunks_processed": 12,
    "recursion_depth": 2,
    "processing_time_ms": 3200
  }
}
```

---

## 💡 Pro Tips

1. **Start with Phase 1 only** - Don't try to implement everything at once
2. **Test incrementally** - After each function, test it independently
3. **Use small contexts first** - Test with 50 messages before trying 500
4. **Compare quality** - Run same query with/without RLM to verify improvement
5. **Monitor costs** - Track token usage to optimize chunk sizes
6. **Cache aggressively** - Cache recursive results to avoid reprocessing
7. **Stream to UI** - Show progressive results instead of waiting for completion

---

## 📖 Related Documentation

- **Full RLM Guide**: `RLM_INTEGRATION_GUIDE.md` (this repo)
- **Current Memory System**: `HIERARCHICAL_MEMORY_GUIDE.md` (this repo)
- **MIT RLM Paper**: https://arxiv.org/pdf/2512.24601
- **Implementation Checklist**: See Phase 1-5 in full guide

---

## ❓ FAQ

**Q: Will RLM replace hierarchical memory?**  
A: No! RLM **augments** it. Hierarchical memory still handles storage/retrieval, RLM adds intelligent processing of long contexts.

**Q: How much will this cost (token-wise)?**  
A: For 500 messages: ~50k tokens with RLM vs ~200k tokens trying to fit everything in context. RLM is often cheaper.

**Q: What if I don't have access to GPT-4?**  
A: Use any LLM! RLM works with local models too. Just adjust chunk sizes based on your model's context window.

**Q: Will this work with encrypted medical data?**  
A: Yes! RLM processes data after decryption, so encryption is transparent.

**Q: How long to implement?**  
A: Basic version (Phase 1): 1 week. Full-featured (Phases 1-5): 5 weeks.

---

## 🎉 Summary

**What you're building**: A system that lets AuraNexus handle unlimited conversation length by recursively processing context in chunks.

**Why it matters**: No more context limits, better summaries, smarter retrieval, cross-session intelligence.

**How to start**: Follow Phase 1 checklist, test with 100-message conversation, verify coherent summary.

**Next step**: Read `RLM_INTEGRATION_GUIDE.md` for full implementation details.

Good luck! 🚀
