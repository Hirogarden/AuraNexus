# KoboldCPP GGUF Loading Patterns Harvest

**Source:** LostRuins/koboldcpp  
**Purpose:** Extract professional patterns for GGUF model loading, memory management, and GPU offloading  
**Target:** Improve local model handling in AuraNexus

---

## Overview

KoboldCPP is a mature C++ implementation that provides excellent patterns for:
- GGUF file parsing and metadata extraction
- Memory size calculation before loading
- GPU layer offloading with VRAM tracking
- Low VRAM optimization modes
- Model architecture detection
- Context initialization

---

## 1. GGUF Initialization Pattern

### Basic File Loading
```cpp
// Initialize with no_alloc=true to read metadata only
struct gguf_init_params params = {
    .no_alloc = true,
    .ctx = &ctx_meta
};
ctx_gguf = gguf_init_from_file(file_path.c_str(), params);
```

**Python Equivalent Strategy:**
```python
# Read GGUF metadata without loading full model
import struct
import mmap

def read_gguf_metadata(filepath):
    with open(filepath, 'rb') as f:
        # Read magic number (4 bytes)
        magic = struct.unpack('<I', f.read(4))[0]
        assert magic == 0x46554747, "Not a GGUF file"
        
        # Read version (4 bytes)
        version = struct.unpack('<I', f.read(4))[0]
        
        # Read tensor count and metadata count
        n_tensors = struct.unpack('<Q', f.read(8))[0]
        n_kv = struct.unpack('<Q', f.read(8))[0]
        
        return {
            'version': version,
            'n_tensors': n_tensors,
            'n_kv': n_kv
        }
```

---

## 2. Architecture Detection

### KoboldCPP Pattern
```cpp
std::string gguf_get_model_arch(const std::string & gguf_filename) {
    struct gguf_init_params ggufparams;
    ggufparams.no_alloc = true;
    ggufparams.ctx = NULL;
    struct gguf_context * ctx = gguf_init_from_file(gguf_filename.c_str(), ggufparams);
    if (!ctx) return "";
    auto keyidx = gguf_find_key(ctx, "general.architecture");
    std::string modelarch = "";
    if (keyidx != -1) { modelarch = gguf_get_val_str(ctx, keyidx); }
    gguf_free(ctx);
    return modelarch;
}
```

**Supported Architectures:**
- `llama`, `llama4`, `deci`
- `falcon`, `falcon-h1`
- `qwen2`, `qwen2vl`
- `gemma3`, `gemma3n`
- `mamba`, `mamba2`, `jamba` (RNN-style)
- `rwkv6`, `rwkv7`
- `glm4`, `glm4moe`
- `phi`
- And many more...

**Python Application:**
```python
def detect_model_architecture(gguf_path: str) -> str:
    """Detect GGUF model architecture from metadata."""
    # Use gguf-py library or parse manually
    import gguf
    reader = gguf.GGUFReader(gguf_path)
    
    # Look for general.architecture key
    for field in reader.fields.values():
        if field.name == 'general.architecture':
            return str(field.parts[0])
    
    return "unknown"
```

---

## 3. Memory Calculation Strategy

### Context Size Calculation
```cpp
// Calculate memory needed for model context
ctx_size = 0;
ctx_size += n_embd * ggml_type_sizef(GGML_TYPE_F32);  // embeddings
ctx_size += n_ctx * n_layer * n_embd * ggml_type_sizef(memory_type);  // memory_k
ctx_size += n_ctx * n_layer * n_embd * ggml_type_sizef(memory_type);  // memory_v

// Add layer weights
ctx_size += n_layer * (4*n_embd*n_embd * ggml_type_size(wtype));  // attention
ctx_size += n_layer * (4*n_embd*n_embd * ggml_type_size(wtype));  // mlp

// Object overhead
ctx_size += (6 + 12*n_layer) * 1024;

printf("ggml ctx size = %6.2f MB\n", ctx_size/(1024.0*1024.0));
```

**Key Principles:**
1. **Embeddings**: `n_embd * 4 bytes` (F32)
2. **KV Cache**: `n_ctx * n_layer * n_embd * type_size * 2` (K and V)
3. **Layer Weights**: Depends on quantization type
4. **Overhead**: ~1KB per layer + base overhead

**Python Implementation Strategy:**
```python
def estimate_model_memory(
    n_vocab: int,
    n_ctx: int,
    n_embd: int,
    n_layer: int,
    ftype: str  # e.g., "Q4_0", "Q8_0", "F16"
) -> dict:
    """Estimate memory requirements for GGUF model."""
    
    # Type sizes in bytes
    TYPE_SIZES = {
        'F32': 4,
        'F16': 2,
        'Q8_0': 1.125,  # 8-bit + overhead
        'Q4_0': 0.625,  # 4-bit + overhead
        'Q4_1': 0.6875,
        'Q5_0': 0.75,
        'Q5_1': 0.8125,
    }
    
    base_type = TYPE_SIZES.get(ftype, 2)  # Default to F16
    
    # Embeddings (always F32)
    embeddings_size = n_vocab * n_embd * 4
    
    # KV Cache (typically F16)
    kv_cache_size = 2 * n_ctx * n_layer * n_embd * 2
    
    # Model weights
    weights_size = n_layer * (
        # Attention weights
        4 * n_embd * n_embd * base_type +
        # MLP weights  
        4 * n_embd * n_embd * base_type
    )
    
    # Overhead
    overhead = (6 + 12 * n_layer) * 1024
    
    total = embeddings_size + kv_cache_size + weights_size + overhead
    
    return {
        'embeddings_mb': embeddings_size / (1024 * 1024),
        'kv_cache_mb': kv_cache_size / (1024 * 1024),
        'weights_mb': weights_size / (1024 * 1024),
        'overhead_mb': overhead / (1024 * 1024),
        'total_mb': total / (1024 * 1024),
        'total_gb': total / (1024 * 1024 * 1024)
    }
```

---

## 4. GPU Layer Offloading

### KoboldCPP Offloading Strategy
```cpp
// Determine how many layers to offload
if (gpulayers > 0) {
    const int n_gpu = std::min(gpulayers, int(hparams.n_layer));
    size_t vram_total = 0;
    
    fprintf(stderr, "[opencl] offloading %d layers to GPU\n", n_gpu);
    
    // Track VRAM usage per tensor
    vram_total += ggml_nbytes(model.output);
    
    fprintf(stderr, "[opencl] total VRAM used: %zu MB\n", 
            vram_total / 1024 / 1024);
}
```

**Layer Split Configuration:**
```cpp
#if defined(GGML_USE_CUDA)
// Row split for multi-GPU (better for large models)
model_params.split_mode = (inputs.use_rowsplit 
    ? llama_split_mode::LLAMA_SPLIT_MODE_ROW 
    : llama_split_mode::LLAMA_SPLIT_MODE_LAYER);
#else
// Layer split only
model_params.split_mode = llama_split_mode::LLAMA_SPLIT_MODE_LAYER;
#endif
```

**Python Application (via Ollama API):**
```python
async def optimize_gpu_layers(
    model_info: dict,
    available_vram_gb: float
) -> int:
    """Calculate optimal GPU layer count based on VRAM."""
    
    # Extract model parameters
    n_layer = model_info.get('n_layer', 32)
    
    # Estimate VRAM per layer (rough approximation)
    mem_estimate = estimate_model_memory(
        n_vocab=model_info.get('n_vocab', 32000),
        n_ctx=model_info.get('n_ctx', 2048),
        n_embd=model_info.get('n_embd', 4096),
        n_layer=n_layer,
        ftype=model_info.get('ftype', 'Q4_0')
    )
    
    mb_per_layer = mem_estimate['weights_mb'] / n_layer
    available_vram_mb = available_vram_gb * 1024
    
    # Reserve some VRAM for overhead (20%)
    usable_vram_mb = available_vram_mb * 0.8
    
    # Calculate layers that fit
    max_layers = int(usable_vram_mb / mb_per_layer)
    
    return min(max_layers, n_layer)

# Example usage
gpu_layers = await optimize_gpu_layers(
    model_info={'n_layer': 32, 'n_embd': 4096, 'ftype': 'Q4_0'},
    available_vram_gb=8  # RTX 5060 Laptop
)
```

---

## 5. Low VRAM Mode

### KoboldCPP Low VRAM Strategy
```cpp
llama_ctx_params.low_vram = inputs.low_vram;
llama_ctx_params.offload_kqv = !inputs.low_vram;  // Don't offload KV cache in low VRAM

// For low VRAM, reduce batch size
if (inputs.low_vram) {
    kcpp_data->n_batch = std::min(kcpp_data->n_batch, 256);
}
```

**Key Optimizations:**
1. **KV Cache**: Keep on CPU when VRAM limited
2. **Batch Size**: Reduce to 256 or lower
3. **Context Size**: Limit max context
4. **Layer Split**: Partial GPU offload

**Python Implementation:**
```python
class LowVRAMOptimizer:
    """Optimize model loading for low VRAM scenarios."""
    
    def __init__(self, vram_gb: float = 8.0):
        self.vram_gb = vram_gb
        self.is_low_vram = vram_gb <= 8
    
    def get_optimal_params(self, model_size_gb: float) -> dict:
        """Get optimal parameters for model loading."""
        
        if not self.is_low_vram:
            return {
                'gpu_layers': -1,  # All layers
                'n_batch': 512,
                'n_ctx': 8192,
                'offload_kqv': True
            }
        
        # Low VRAM mode
        # Estimate layers that fit
        usable_vram = self.vram_gb * 0.7  # Reserve 30%
        gpu_layers = int((usable_vram / model_size_gb) * 32)  # Assume 32 layers
        
        return {
            'gpu_layers': max(0, min(gpu_layers, 20)),  # Cap at 20 layers
            'n_batch': 128,  # Smaller batches
            'n_ctx': 4096,   # Reduced context
            'offload_kqv': False  # Keep KV cache on CPU
        }

# Example
optimizer = LowVRAMOptimizer(vram_gb=8)
params = optimizer.get_optimal_params(model_size_gb=4.7)
# Returns: {'gpu_layers': 12, 'n_batch': 128, 'n_ctx': 4096, 'offload_kqv': False}
```

---

## 6. Model Parameter Reading

### Hyperparameter Extraction
```cpp
// Read model hparams from binary file
fin.read((char *) &hparams.n_vocab, sizeof(hparams.n_vocab));
fin.read((char *) &hparams.n_ctx,   sizeof(hparams.n_ctx));
fin.read((char *) &hparams.n_embd,  sizeof(hparams.n_embd));
fin.read((char *) &hparams.n_head,  sizeof(hparams.n_head));
fin.read((char *) &hparams.n_layer, sizeof(hparams.n_layer));
fin.read((char *) &hparams.ftype,   sizeof(hparams.ftype));

// Quantization version
const int32_t qntvr = hparams.ftype / GGML_QNT_VERSION_FACTOR;
```

**GGUF Metadata Keys:**
```cpp
// Context from metadata
fkey = modelarch + ".context_length";
keyidx = gguf_find_key(ctx, fkey.c_str());
if (keyidx != -1) {
    n_ctx_train = gguf_get_val_u32(ctx, keyidx);
}

// Expert count (for MoE models)
fkey = modelarch + ".expert_count";
keyidx = gguf_find_key(ctx, fkey.c_str());
if (keyidx != -1) {
    n_expert_count = gguf_get_val_u32(ctx, keyidx);
}

// RoPE frequency base
fkey = modelarch + ".rope.freq_base";
keyidx = gguf_find_key(ctx, fkey.c_str());
if (keyidx != -1) {
    freq_base = gguf_get_val_f32(ctx, keyidx);
}
```

**Python Metadata Parser:**
```python
def extract_model_metadata(gguf_path: str) -> dict:
    """Extract comprehensive metadata from GGUF file."""
    import gguf
    
    reader = gguf.GGUFReader(gguf_path)
    
    # Detect architecture first
    arch = None
    for field in reader.fields.values():
        if field.name == 'general.architecture':
            arch = str(field.parts[0])
            break
    
    if not arch:
        return {}
    
    # Extract architecture-specific parameters
    metadata = {'architecture': arch}
    
    # Common keys
    keys_to_extract = {
        f'{arch}.context_length': 'n_ctx',
        f'{arch}.embedding_length': 'n_embd',
        f'{arch}.block_count': 'n_layer',
        f'{arch}.attention.head_count': 'n_head',
        f'{arch}.rope.freq_base': 'rope_freq_base',
        f'{arch}.expert_count': 'n_expert',
        'general.file_type': 'ftype',
        'general.quantization_version': 'quant_version'
    }
    
    for field in reader.fields.values():
        for gguf_key, meta_key in keys_to_extract.items():
            if field.name == gguf_key:
                metadata[meta_key] = field.parts[0]
    
    return metadata
```

---

## 7. Context Initialization

### Memory Buffer Setup
```cpp
struct ggml_init_params params = {
    .mem_size = ctx_size,
    .mem_buffer = NULL,  // Let ggml allocate
    .no_alloc = false
};

model.ctx = ggml_init(params);
if (!model.ctx) {
    fprintf(stderr, "ggml_init() failed\n");
    return FAIL;
}
```

### With Memory Mapping
```cpp
// Use mmap for large files
llama_v3_model_loader loader(fname_base, use_mmap);

loader.calc_sizes(&ctx_size, &mmapped_size);
printf("ctx size = %7.2f MB\n", ctx_size/1024.0/1024.0);

// Allocate based on mmap support
*(use_mmap ? &mmapped_size : &ctx_size) += tensor.size + 16;
```

**Python Strategy (via Ollama):**
```python
# Ollama handles memory management internally
# But we can configure through model parameters

async def load_model_with_memory_config(
    client: AsyncOllamaClient,
    model: str,
    use_mmap: bool = True,
    use_mlock: bool = False
) -> dict:
    """Load model with memory configuration."""
    
    # Note: Ollama abstracts this, but we can pass via environment
    # or through model file configuration
    
    modelfile = f"""
FROM {model}
PARAMETER mmap {str(use_mmap).lower()}
PARAMETER mlock {str(use_mlock).lower()}
PARAMETER num_ctx 4096
"""
    
    try:
        # Create configured model
        response = await client.create(
            name=f"{model}-optimized",
            modelfile=modelfile
        )
        return response
    except Exception as e:
        print(f"Model config failed: {e}")
        return {}
```

---

## 8. Tensor Loading Loop

### Progressive Loading Pattern
```cpp
while (true) {
    int32_t n_dims, length, ttype;
    
    // Read tensor metadata
    fin.read(reinterpret_cast<char *>(&n_dims), sizeof(n_dims));
    fin.read(reinterpret_cast<char *>(&length), sizeof(length));
    fin.read(reinterpret_cast<char *>(&ttype),  sizeof(ttype));
    
    if (fin.eof()) break;
    
    // Validate
    assert(n_dims >= 0 && n_dims <= 4, "Invalid tensor dimensions");
    assert(length < 4096, "Absurd tensor name length");
    
    // Read dimensions
    uint32_t dims[4];
    fin.read(reinterpret_cast<char *>(dims), n_dims * sizeof(uint32_t));
    
    // Read tensor name
    char name[4096];
    fin.read(name, length);
    
    // Alignment padding
    size_t offset = fin.tellg();
    size_t pad = ((offset + 31) & ~31) - offset;
    fin.seekg(pad, std::ios::cur);
    
    // Read tensor data...
}
```

**Python Progressive Loading:**
```python
async def monitor_model_loading(
    client: AsyncOllamaClient,
    model: str,
    callback: callable = None
) -> None:
    """Monitor model loading progress."""
    
    # Ollama provides progress through pull/create responses
    async for progress in client.pull(model, stream=True):
        status = progress.get('status', '')
        
        if 'total' in progress and 'completed' in progress:
            percent = (progress['completed'] / progress['total']) * 100
            
            if callback:
                callback(status, percent)
            else:
                print(f"{status}: {percent:.1f}%")
```

---

## 9. VRAM Usage Tracking

### Real-Time VRAM Monitoring
```cpp
size_t vram_total = 0;

// Track each offloaded tensor
vram_total += ggml_nbytes(model.output);
vram_total += ggml_nbytes(model.tok_embeddings);

for (auto& layer : model.layers) {
    vram_total += ggml_nbytes(layer.attention_norm);
    vram_total += ggml_nbytes(layer.wq);
    vram_total += ggml_nbytes(layer.wk);
    // ... all layer tensors
}

fprintf(stderr, "Total VRAM used: %zu MB\n", vram_total / 1024 / 1024);
```

**Python VRAM Monitor:**
```python
import subprocess
import re

class VRAMMonitor:
    """Monitor NVIDIA GPU VRAM usage."""
    
    def __init__(self):
        self.total_vram_mb = self._get_total_vram()
    
    def _get_total_vram(self) -> float:
        """Get total VRAM in MB."""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                capture_output=True, text=True
            )
            return float(result.stdout.strip())
        except:
            return 8192.0  # Default 8GB
    
    def get_current_usage(self) -> dict:
        """Get current VRAM usage."""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used,memory.free', 
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True
            )
            used, free = map(float, result.stdout.strip().split(','))
            
            return {
                'used_mb': used,
                'free_mb': free,
                'total_mb': self.total_vram_mb,
                'used_percent': (used / self.total_vram_mb) * 100
            }
        except:
            return {'used_mb': 0, 'free_mb': self.total_vram_mb, 'total_mb': self.total_vram_mb}
    
    def can_fit_model(self, model_size_mb: float) -> tuple[bool, str]:
        """Check if model can fit in available VRAM."""
        usage = self.get_current_usage()
        free_mb = usage['free_mb']
        
        # Need 20% buffer for operations
        required_mb = model_size_mb * 1.2
        
        if required_mb <= free_mb:
            return True, f"Model fits: {required_mb:.0f}MB needed, {free_mb:.0f}MB available"
        else:
            # Calculate how many layers could fit
            layers_possible = int((free_mb / required_mb) * 32)  # Assume 32 layers
            return False, f"Only {layers_possible} layers can fit (need {required_mb:.0f}MB, have {free_mb:.0f}MB)"

# Usage
monitor = VRAMMonitor()
can_fit, msg = monitor.can_fit_model(4700)  # 4.7GB model
print(msg)
```

---

## 10. Practical Integration Strategy

### For AuraNexus Application

**1. Pre-Load Memory Check:**
```python
async def safe_model_load(
    client: AsyncOllamaClient,
    model_name: str
) -> dict:
    """Safely load model with memory checks."""
    
    # Get model info first
    model_info = await client.show(model_name)
    model_size_gb = model_info.get('size', 0) / (1024**3)
    
    # Check VRAM availability
    vram_monitor = VRAMMonitor()
    can_fit, msg = vram_monitor.can_fit_model(model_size_gb * 1024)
    
    if not can_fit:
        # Use low VRAM optimizer
        optimizer = LowVRAMOptimizer(vram_gb=8)
        params = optimizer.get_optimal_params(model_size_gb)
        
        # Create optimized model variant
        modelfile = f"""
FROM {model_name}
PARAMETER num_gpu {params['gpu_layers']}
PARAMETER num_batch {params['n_batch']}
PARAMETER num_ctx {params['n_ctx']}
"""
        await client.create(f"{model_name}-lowvram", modelfile)
        model_name = f"{model_name}-lowvram"
    
    return {'model': model_name, 'optimization': params if not can_fit else {}}
```

**2. Architecture-Aware Loading:**
```python
async def load_with_architecture_detection(
    client: AsyncOllamaClient,
    model_name: str
) -> dict:
    """Load model with architecture-specific optimizations."""
    
    # Get model details
    details = await client.show(model_name)
    
    # Extract architecture from modelfile or parameters
    arch = 'llama'  # Default
    if 'modelfile' in details:
        # Parse architecture from modelfile
        pass
    
    # Architecture-specific optimizations
    arch_configs = {
        'qwen2': {'flash_attn': True, 'rope_scale': 1.0},
        'gemma': {'num_gqa': 8},
        'mamba': {'conv_kernel': 4},  # RNN-style
    }
    
    config = arch_configs.get(arch, {})
    return {'architecture': arch, 'config': config}
```

**3. Progressive Loading with Feedback:**
```python
async def load_model_with_progress(
    client: AsyncOllamaClient,
    model_name: str,
    progress_callback: callable
) -> None:
    """Load model with real-time progress feedback."""
    
    async for chunk in client.pull(model_name, stream=True):
        if 'status' in chunk:
            status = chunk['status']
            
            if 'total' in chunk and 'completed' in chunk:
                progress = (chunk['completed'] / chunk['total']) * 100
                progress_callback(f"{status}: {progress:.1f}%")
            else:
                progress_callback(status)
```

---

## Key Takeaways for Implementation

### Immediate Priorities (User has RTX 5060 8GB VRAM):

1. **Low VRAM Mode Essential:**
   - Implement automatic detection of VRAM capacity
   - Cap GPU layers at 12-20 for 4-8GB models
   - Keep KV cache on CPU
   - Reduce batch size to 128-256

2. **Memory Estimation:**
   - Calculate required memory before loading
   - Warn user if model won't fit
   - Suggest layer count adjustments

3. **VRAM Monitoring:**
   - Real-time tracking during loading
   - Prevent OOM crashes
   - Dynamic layer adjustment

4. **Architecture Detection:**
   - Parse GGUF metadata
   - Apply architecture-specific optimizations
   - Handle special cases (Qwen2, Mamba, etc.)

### Future Enhancements:

1. **Smart Layer Splitting:**
   - Analyze which layers to offload (attention vs MLP)
   - Optimize for specific hardware

2. **Context Caching:**
   - Reuse KV cache between sessions
   - Reduce memory churn

3. **Model Quantization:**
   - On-the-fly requantization for VRAM fit
   - Q8 → Q4 conversion when needed

---

## References

- **KoboldCPP Repository:** https://github.com/LostRuins/koboldcpp
- **GGUF Specification:** Part of ggml library
- **Memory Patterns:** Based on otherarch/*.cpp implementations
- **GPU Offloading:** From src/llama-context.cpp and gpttype_adapter.cpp

---

*Document created: 2024 - Part of AuraNexus Repository Harvest Initiative*
