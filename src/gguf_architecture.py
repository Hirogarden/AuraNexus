"""
GGUF Architecture Detection and Optimization
Based on KoboldCPP's comprehensive architecture support
"""

import struct
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class Architecture(Enum):
    """Supported model architectures from KoboldCPP."""
    # Transformer architectures
    LLAMA = "llama"
    LLAMA4 = "llama4"
    DECI = "deci"
    FALCON = "falcon"
    FALCON_H1 = "falcon-h1"
    QWEN2 = "qwen2"
    QWEN2VL = "qwen2vl"
    GEMMA3 = "gemma3"
    GEMMA3N = "gemma3n"
    PHI = "phi"
    GLM4 = "glm4"
    GLM4MOE = "glm4moe"
    MISTRAL = "mistral"
    MIXTRAL = "mixtral"
    
    # RNN-style architectures
    MAMBA = "mamba"
    MAMBA2 = "mamba2"
    JAMBA = "jamba"
    RWKV6 = "rwkv6"
    RWKV7 = "rwkv7"
    
    # Other
    UNKNOWN = "unknown"
    
    @classmethod
    def from_string(cls, arch_str: str) -> 'Architecture':
        """Convert string to Architecture enum."""
        for arch in cls:
            if arch.value == arch_str.lower():
                return arch
        return cls.UNKNOWN


@dataclass
class ModelMetadata:
    """Complete model metadata from GGUF file."""
    architecture: Architecture
    n_ctx: Optional[int] = None          # Context length
    n_embd: Optional[int] = None         # Embedding dimension
    n_layer: Optional[int] = None        # Number of layers
    n_head: Optional[int] = None         # Attention heads
    n_head_kv: Optional[int] = None      # Key-value heads (for GQA)
    n_vocab: Optional[int] = None        # Vocabulary size
    rope_freq_base: Optional[float] = None
    n_expert: Optional[int] = None       # For MoE models
    n_expert_used: Optional[int] = None  # Active experts per token
    ftype: Optional[int] = None          # Quantization type
    quant_version: Optional[int] = None
    
    # File info
    file_path: Optional[str] = None
    file_size_mb: Optional[float] = None
    
    def is_moe(self) -> bool:
        """Check if this is a Mixture of Experts model."""
        return self.n_expert is not None and self.n_expert > 1
    
    def is_rnn_style(self) -> bool:
        """Check if this is an RNN-style architecture (Mamba, RWKV, etc.)."""
        return self.architecture in {
            Architecture.MAMBA,
            Architecture.MAMBA2,
            Architecture.JAMBA,
            Architecture.RWKV6,
            Architecture.RWKV7
        }
    
    def has_gqa(self) -> bool:
        """Check if model uses Grouped Query Attention."""
        return (
            self.n_head is not None and 
            self.n_head_kv is not None and 
            self.n_head_kv < self.n_head
        )
    
    def get_kv_ratio(self) -> float:
        """Get KV head to query head ratio (for GQA memory estimation)."""
        if not self.has_gqa():
            return 1.0
        return self.n_head_kv / self.n_head


class GGUFReader:
    """
    Lightweight GGUF metadata reader.
    Only reads header and metadata without loading tensors.
    Based on KoboldCPP's no_alloc pattern.
    """
    
    GGUF_MAGIC = 0x46554747  # "GGUF"
    
    # GGUF value types
    GGUF_TYPE_UINT8 = 0
    GGUF_TYPE_INT8 = 1
    GGUF_TYPE_UINT16 = 2
    GGUF_TYPE_INT16 = 3
    GGUF_TYPE_UINT32 = 4
    GGUF_TYPE_INT32 = 5
    GGUF_TYPE_FLOAT32 = 6
    GGUF_TYPE_BOOL = 7
    GGUF_TYPE_STRING = 8
    GGUF_TYPE_ARRAY = 9
    GGUF_TYPE_UINT64 = 10
    GGUF_TYPE_INT64 = 11
    GGUF_TYPE_FLOAT64 = 12
    
    def __init__(self, path: str):
        """Initialize reader with GGUF file path."""
        self.path = Path(path)
        self.metadata: Dict[str, any] = {}
        self._read_metadata()
    
    def _read_metadata(self):
        """Read GGUF metadata without loading tensors."""
        with open(self.path, 'rb') as f:
            # Read magic
            magic = struct.unpack('<I', f.read(4))[0]
            if magic != self.GGUF_MAGIC:
                raise ValueError(f"Not a GGUF file: invalid magic number {hex(magic)}")
            
            # Read version
            version = struct.unpack('<I', f.read(4))[0]
            if version not in [2, 3]:
                raise ValueError(f"Unsupported GGUF version: {version}")
            
            # Read counts
            n_tensors = struct.unpack('<Q', f.read(8))[0]
            n_kv = struct.unpack('<Q', f.read(8))[0]
            
            # Read key-value pairs
            for _ in range(n_kv):
                key = self._read_string(f)
                value_type = struct.unpack('<I', f.read(4))[0]
                value = self._read_value(f, value_type)
                
                if key and value is not None:
                    self.metadata[key] = value
    
    def _read_string(self, f) -> str:
        """Read a string from GGUF file."""
        length = struct.unpack('<Q', f.read(8))[0]
        if length > 0:
            return f.read(length).decode('utf-8', errors='ignore')
        return ""
    
    def _read_value(self, f, value_type: int):
        """Read a value based on its type."""
        if value_type == self.GGUF_TYPE_UINT8:
            return struct.unpack('<B', f.read(1))[0]
        elif value_type == self.GGUF_TYPE_INT8:
            return struct.unpack('<b', f.read(1))[0]
        elif value_type == self.GGUF_TYPE_UINT16:
            return struct.unpack('<H', f.read(2))[0]
        elif value_type == self.GGUF_TYPE_INT16:
            return struct.unpack('<h', f.read(2))[0]
        elif value_type == self.GGUF_TYPE_UINT32:
            return struct.unpack('<I', f.read(4))[0]
        elif value_type == self.GGUF_TYPE_INT32:
            return struct.unpack('<i', f.read(4))[0]
        elif value_type == self.GGUF_TYPE_FLOAT32:
            return struct.unpack('<f', f.read(4))[0]
        elif value_type == self.GGUF_TYPE_UINT64:
            return struct.unpack('<Q', f.read(8))[0]
        elif value_type == self.GGUF_TYPE_INT64:
            return struct.unpack('<q', f.read(8))[0]
        elif value_type == self.GGUF_TYPE_FLOAT64:
            return struct.unpack('<d', f.read(8))[0]
        elif value_type == self.GGUF_TYPE_BOOL:
            return struct.unpack('<?', f.read(1))[0]
        elif value_type == self.GGUF_TYPE_STRING:
            return self._read_string(f)
        elif value_type == self.GGUF_TYPE_ARRAY:
            # Skip arrays for now (complex to parse)
            array_type = struct.unpack('<I', f.read(4))[0]
            array_len = struct.unpack('<Q', f.read(8))[0]
            # TODO: Implement array reading if needed
            return None
        
        return None
    
    def get(self, key: str, default=None):
        """Get metadata value by key."""
        return self.metadata.get(key, default)


class ArchitectureDetector:
    """
    Detect and analyze model architecture from GGUF files.
    Based on KoboldCPP's gguf_get_model_arch pattern.
    """
    
    @staticmethod
    def detect_from_file(path: str) -> ModelMetadata:
        """
        Detect architecture and extract metadata from GGUF file.
        
        Args:
            path: Path to GGUF file
            
        Returns:
            ModelMetadata with architecture and parameters
        """
        reader = GGUFReader(path)
        
        # Detect architecture first
        arch_str = reader.get('general.architecture', 'unknown')
        architecture = Architecture.from_string(arch_str)
        
        # Create metadata object
        metadata = ModelMetadata(
            architecture=architecture,
            file_path=path,
            file_size_mb=Path(path).stat().st_size / (1024 * 1024)
        )
        
        # Extract architecture-specific parameters
        prefix = arch_str if arch_str != 'unknown' else 'llama'
        
        # Common parameters
        metadata.n_ctx = reader.get(f'{prefix}.context_length')
        metadata.n_embd = reader.get(f'{prefix}.embedding_length')
        metadata.n_layer = reader.get(f'{prefix}.block_count')
        metadata.n_head = reader.get(f'{prefix}.attention.head_count')
        metadata.n_head_kv = reader.get(f'{prefix}.attention.head_count_kv')
        metadata.n_vocab = reader.get('tokenizer.ggml.token_count')  # Common location
        metadata.rope_freq_base = reader.get(f'{prefix}.rope.freq_base')
        
        # MoE parameters
        metadata.n_expert = reader.get(f'{prefix}.expert_count')
        metadata.n_expert_used = reader.get(f'{prefix}.expert_used_count')
        
        # Quantization info
        metadata.ftype = reader.get('general.file_type')
        metadata.quant_version = reader.get('general.quantization_version')
        
        return metadata
    
    @staticmethod
    def get_optimization_hints(metadata: ModelMetadata) -> Dict[str, any]:
        """
        Get architecture-specific optimization hints.
        Based on KoboldCPP's per-architecture handling.
        
        Returns:
            Dictionary of optimization parameters
        """
        hints = {
            'supports_flash_attn': True,
            'supports_mqa': False,
            'supports_gqa': False,
            'kv_cache_multiplier': 1.0,
            'recommended_batch_size': 512,
            'offload_priority': 'all'  # all, attention_only, mlp_priority
        }
        
        # RNN-style models (Mamba, RWKV)
        if metadata.is_rnn_style():
            hints['supports_flash_attn'] = False  # Different attention mechanism
            hints['kv_cache_multiplier'] = 0.5     # Smaller state size
            hints['recommended_batch_size'] = 1024  # Can handle larger batches
            hints['offload_priority'] = 'sequential'  # Sequential processing
        
        # MoE models (Mixtral, etc.)
        elif metadata.is_moe():
            hints['kv_cache_multiplier'] = 1.5      # Experts add overhead
            hints['recommended_batch_size'] = 256   # Smaller batches for MoE
            hints['offload_priority'] = 'mlp_priority'  # Offload expert layers first
        
        # Grouped Query Attention (Llama 2/3, Qwen2, etc.)
        elif metadata.has_gqa():
            hints['supports_gqa'] = True
            hints['kv_cache_multiplier'] = metadata.get_kv_ratio()  # Reduced KV cache
            hints['recommended_batch_size'] = 512
        
        # Multi-Query Attention (Falcon)
        elif metadata.architecture in {Architecture.FALCON, Architecture.FALCON_H1}:
            hints['supports_mqa'] = True
            hints['kv_cache_multiplier'] = 0.25     # Much smaller KV cache
            hints['recommended_batch_size'] = 1024
        
        return hints
    
    @staticmethod
    def format_summary(metadata: ModelMetadata) -> str:
        """Format a human-readable summary of the model."""
        lines = [
            f"Architecture: {metadata.architecture.value.upper()}",
            f"File: {Path(metadata.file_path).name if metadata.file_path else 'Unknown'}",
            f"Size: {metadata.file_size_mb:.2f} MB" if metadata.file_size_mb else "Size: Unknown",
        ]
        
        if metadata.n_layer:
            lines.append(f"Layers: {metadata.n_layer}")
        
        if metadata.n_ctx:
            lines.append(f"Context: {metadata.n_ctx:,} tokens")
        
        if metadata.n_embd:
            lines.append(f"Embedding: {metadata.n_embd} dim")
        
        if metadata.n_head:
            head_info = f"Heads: {metadata.n_head}"
            if metadata.n_head_kv and metadata.n_head_kv != metadata.n_head:
                head_info += f" (KV: {metadata.n_head_kv}, GQA ratio: {metadata.get_kv_ratio():.2f})"
            lines.append(head_info)
        
        if metadata.is_moe():
            lines.append(f"MoE: {metadata.n_expert} experts ({metadata.n_expert_used} active)")
        
        if metadata.is_rnn_style():
            lines.append("Type: RNN-style (efficient inference)")
        
        return "\n".join(lines)


# Convenience functions
def detect_architecture(gguf_path: str) -> Architecture:
    """Quick architecture detection."""
    metadata = ArchitectureDetector.detect_from_file(gguf_path)
    return metadata.architecture


def get_model_info(gguf_path: str) -> Tuple[ModelMetadata, Dict]:
    """Get complete model info with optimization hints."""
    metadata = ArchitectureDetector.detect_from_file(gguf_path)
    hints = ArchitectureDetector.get_optimization_hints(metadata)
    return metadata, hints


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python gguf_architecture.py <path_to_gguf_file>")
        sys.exit(1)
    
    gguf_path = sys.argv[1]
    
    try:
        print("Analyzing GGUF file...")
        metadata = ArchitectureDetector.detect_from_file(gguf_path)
        hints = ArchitectureDetector.get_optimization_hints(metadata)
        
        print("\n" + "="*60)
        print(ArchitectureDetector.format_summary(metadata))
        print("="*60)
        
        print("\nOptimization Hints:")
        for key, value in hints.items():
            print(f"  {key}: {value}")
        
    except FileNotFoundError:
        print(f"Error: File not found: {gguf_path}")
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
