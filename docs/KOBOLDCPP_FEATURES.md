# KoboldCpp Feature Enhancements for AuraNexus

## Key Improvements to Harvest from KoboldCpp

### 1. **Advanced Sampling Methods**
KoboldCpp includes several sampling improvements beyond base llama.cpp:

#### XTC (eXclude Top Choices)
- `xtc_probability`: Probability of XTC sampling (0.0-1.0)
- `xtc_threshold`: Threshold for excluding top choices
- **Benefit**: Better output diversity, reduces repetitive responses

#### DRY (Don't Repeat Yourself) Sampling
- `dry_multiplier`: Penalty multiplier for repetition
- `dry_base`: Base value for DRY penalty
- `dry_allowed_length`: Length before DRY kicks in
- `dry_penalty_last_n`: How many tokens to look back
- `dry_sequence_breakers`: Tokens that break repetition checking
- **Benefit**: Dramatically reduces repetition without hurting quality

#### Dynamic Temperature
- `dynatemp_range`: Range for dynamic temperature
- `dynatemp_exponent`: Exponent for temperature curve
- **Benefit**: Adapts temperature based on confidence

#### Top-N-Sigma
- `top_n_sigma`: Standard deviations for top-n sampling
- **Benefit**: Better quality control for sampling

### 2. **Smart Context Management**
```cpp
// KoboldCpp feature: Keep important parts when context fills
n_keep    // Keep first N tokens (system prompt)
n_discard // Discard middle tokens when full
```
**Benefit**: Don't lose system prompt or recent context when context window fills

### 3. **Grammar/Format Enforcement**
```python
# Built-in JSON schema to grammar conversion
grammar = json_schema_to_grammar(schema)
```
**Benefit**: Guaranteed valid JSON/structured outputs

### 4. **Better Model Compatibility**
KoboldCpp supports:
- Llama (all versions)
- Mistral, Mixtral
- Phi, Gemma, Qwen
- Vision models (multimodal)
- Audio models (Whisper integration)

### 5. **Performance Optimizations**
- Flash Attention support
- Multiple GPU backends (CUDA, ROCm, Vulkan, OpenCL)
- Optimized batch processing
- Better memory management

## Implementation Priority

### HIGH PRIORITY (Implement Now)
1. ✅ DRY sampling - Solves repetition problem
2. ✅ XTC sampling - Better diversity
3. ✅ Smart context (n_keep, n_discard)
4. ✅ Dynamic temperature
5. ✅ Grammar enforcement for JSON

### MEDIUM PRIORITY (Next Phase)
6. Vision model support (for image understanding)
7. Speculative decoding (faster generation)
8. Multiple LoRA adapters
9. Advanced memory management

### LOW PRIORITY (Future)
10. Audio/TTS integration
11. Stable Diffusion integration
12. Multi-turn optimization

## Security Considerations

All improvements maintain security:
- ✅ No external process calls
- ✅ No network communication
- ✅ In-process only
- ✅ HIPAA-compliant

## Code References

KoboldCpp source locations:
- Sampling: `src/llama-sampling.cpp`
- Context mgmt: `src/llama-context.cpp`
- Grammar: `json-schema-to-grammar.py`
- Model support: `src/llama-model.cpp`

## Next Steps

1. Create `SecureInferenceEngine` with KoboldCpp enhancements
2. Add advanced sampling parameters to UI
3. Implement smart context management
4. Add grammar/JSON mode
5. Test with various models
