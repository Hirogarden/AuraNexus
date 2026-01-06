"""
Memory Estimation for GGUF Models

Calculates memory requirements before loading models to prevent OOM errors.
Based on KoboldCPP patterns for context size calculation.

Author: AuraNexus
Created: 2026
"""

import struct
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import IntEnum


class GGMLType(IntEnum):
    """GGML quantization types and their sizes."""
    F32 = 0
    F16 = 1
    Q4_0 = 2
    Q4_1 = 3
    Q5_0 = 6
    Q5_1 = 7
    Q8_0 = 8
    Q8_1 = 9
    Q2_K = 10
    Q3_K = 11
    Q4_K = 12
    Q5_K = 13
    Q6_K = 14
    Q8_K = 15


# Type sizes in bytes per element
GGML_TYPE_SIZES = {
    GGMLType.F32: 4.0,
    GGMLType.F16: 2.0,
    GGMLType.Q8_0: 1.125,   # 8-bit + overhead
    GGMLType.Q8_1: 1.25,
    GGMLType.Q4_0: 0.625,   # 4-bit + overhead
    GGMLType.Q4_1: 0.6875,
    GGMLType.Q5_0: 0.75,
    GGMLType.Q5_1: 0.8125,
    GGMLType.Q2_K: 0.3125,
    GGMLType.Q3_K: 0.4375,
    GGMLType.Q4_K: 0.5625,
    GGMLType.Q5_K: 0.6875,
    GGMLType.Q6_K: 0.8125,
    GGMLType.Q8_K: 1.0625,
}


@dataclass
class ModelParams:
    """Model hyperparameters extracted from GGUF."""
    n_vocab: int = 32000
    n_ctx: int = 2048
    n_embd: int = 4096
    n_head: int = 32
    n_layer: int = 32
    ftype: str = "Q4_0"
    architecture: str = "llama"


@dataclass
class MemoryEstimate:
    """Memory requirements breakdown."""
    embeddings_mb: float
    kv_cache_mb: float
    weights_mb: float
    overhead_mb: float
    total_mb: float
    total_gb: float
    
    def __str__(self):
        return (
            f"Memory Estimate:\n"
            f"  Embeddings: {self.embeddings_mb:.2f} MB\n"
            f"  KV Cache: {self.kv_cache_mb:.2f} MB\n"
            f"  Weights: {self.weights_mb:.2f} MB\n"
            f"  Overhead: {self.overhead_mb:.2f} MB\n"
            f"  Total: {self.total_mb:.2f} MB ({self.total_gb:.2f} GB)"
        )


class GGUFMetadataReader:
    """Read GGUF file metadata without loading the full model."""
    
    GGUF_MAGIC = 0x46554747  # "GGUF"
    
    def __init__(self, filepath: str):
        """
        Initialize metadata reader.
        
        Args:
            filepath: Path to GGUF file
        """
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"GGUF file not found: {filepath}")
    
    def read_metadata(self) -> Dict:
        """
        Read GGUF metadata.
        
        Returns:
            Dictionary with metadata key-value pairs
        """
        metadata = {}
        
        try:
            with open(self.filepath, 'rb') as f:
                # Read magic number
                magic = struct.unpack('<I', f.read(4))[0]
                if magic != self.GGUF_MAGIC:
                    raise ValueError(f"Not a GGUF file: magic={hex(magic)}")
                
                # Read version
                version = struct.unpack('<I', f.read(4))[0]
                metadata['version'] = version
                
                # Read tensor count
                n_tensors = struct.unpack('<Q', f.read(8))[0]
                metadata['n_tensors'] = n_tensors
                
                # Read metadata KV count
                n_kv = struct.unpack('<Q', f.read(8))[0]
                metadata['n_kv'] = n_kv
                
                # Read alignment (version 3+)
                if version >= 3:
                    alignment = struct.unpack('<Q', f.read(8))[0]
                    metadata['alignment'] = alignment
                
        except Exception as e:
            print(f"Warning: Could not read GGUF metadata: {e}")
        
        return metadata
    
    def detect_architecture(self) -> str:
        """
        Detect model architecture from filename.
        
        Returns:
            Architecture name (llama, mistral, etc.)
        """
        filename = self.filepath.stem.lower()
        
        # Common architecture patterns
        if 'llama' in filename:
            return 'llama'
        elif 'mistral' in filename or 'mixtral' in filename:
            return 'mistral'
        elif 'qwen' in filename:
            return 'qwen2'
        elif 'gemma' in filename:
            return 'gemma'
        elif 'phi' in filename:
            return 'phi'
        elif 'falcon' in filename:
            return 'falcon'
        
        return 'llama'  # Default
    
    def detect_quantization(self) -> str:
        """
        Detect quantization type from filename.
        
        Returns:
            Quantization type (Q4_0, Q8_0, etc.)
        """
        filename = self.filepath.stem.upper()
        
        # Common quantization patterns
        quant_patterns = ['Q2_K', 'Q3_K', 'Q4_K', 'Q5_K', 'Q6_K', 'Q8_K',
                         'Q4_0', 'Q4_1', 'Q5_0', 'Q5_1', 'Q8_0', 'Q8_1',
                         'F16', 'F32']
        
        for pattern in quant_patterns:
            if pattern in filename:
                return pattern
        
        return 'Q4_0'  # Default


class MemoryEstimator:
    """
    Estimate memory requirements for GGUF models.
    
    Based on KoboldCPP patterns for context size calculation.
    """
    
    def __init__(self):
        """Initialize memory estimator."""
        pass
    
    def estimate_from_params(
        self,
        n_vocab: int,
        n_ctx: int,
        n_embd: int,
        n_layer: int,
        ftype: str = "Q4_0",
        architecture: str = "llama"
    ) -> MemoryEstimate:
        """
        Estimate memory requirements from model parameters.
        
        Args:
            n_vocab: Vocabulary size
            n_ctx: Context window size
            n_embd: Embedding dimension
            n_layer: Number of layers
            ftype: Quantization type (Q4_0, Q8_0, F16, etc.)
            architecture: Model architecture
            
        Returns:
            MemoryEstimate with breakdown
        """
        # Get type size
        type_size = self._get_type_size(ftype)
        
        # Embeddings (always F32 for token embeddings)
        embeddings_size = n_vocab * n_embd * 4  # F32 = 4 bytes
        
        # KV Cache (typically F16)
        # memory_k and memory_v: n_ctx * n_layer * n_embd
        kv_cache_size = 2 * n_ctx * n_layer * n_embd * 2  # F16 = 2 bytes
        
        # Model weights
        weights_size = self._estimate_weights(n_embd, n_layer, type_size, architecture)
        
        # Overhead (per layer + base)
        overhead = (6 + 12 * n_layer) * 1024
        
        # Total
        total_bytes = embeddings_size + kv_cache_size + weights_size + overhead
        
        return MemoryEstimate(
            embeddings_mb=embeddings_size / (1024 * 1024),
            kv_cache_mb=kv_cache_size / (1024 * 1024),
            weights_mb=weights_size / (1024 * 1024),
            overhead_mb=overhead / (1024 * 1024),
            total_mb=total_bytes / (1024 * 1024),
            total_gb=total_bytes / (1024 * 1024 * 1024)
        )
    
    def estimate_from_file(self, filepath: str) -> Tuple[ModelParams, MemoryEstimate]:
        """
        Estimate memory requirements from GGUF file.
        
        Args:
            filepath: Path to GGUF file
            
        Returns:
            Tuple of (ModelParams, MemoryEstimate)
        """
        reader = GGUFMetadataReader(filepath)
        
        # Extract what we can from metadata
        metadata = reader.read_metadata()
        
        # Detect from filename
        architecture = reader.detect_architecture()
        ftype = reader.detect_quantization()
        
        # Use defaults based on common model sizes
        file_size_gb = Path(filepath).stat().st_size / (1024**3)
        params = self._estimate_params_from_size(file_size_gb, architecture, ftype)
        
        estimate = self.estimate_from_params(
            n_vocab=params.n_vocab,
            n_ctx=params.n_ctx,
            n_embd=params.n_embd,
            n_layer=params.n_layer,
            ftype=params.ftype,
            architecture=params.architecture
        )
        
        return params, estimate
    
    def _get_type_size(self, ftype: str) -> float:
        """
        Get size per element for quantization type.
        
        Args:
            ftype: Quantization type string
            
        Returns:
            Bytes per element
        """
        # Map string to enum
        type_map = {
            'F32': GGMLType.F32,
            'F16': GGMLType.F16,
            'Q8_0': GGMLType.Q8_0,
            'Q8_1': GGMLType.Q8_1,
            'Q4_0': GGMLType.Q4_0,
            'Q4_1': GGMLType.Q4_1,
            'Q5_0': GGMLType.Q5_0,
            'Q5_1': GGMLType.Q5_1,
            'Q2_K': GGMLType.Q2_K,
            'Q3_K': GGMLType.Q3_K,
            'Q4_K': GGMLType.Q4_K,
            'Q5_K': GGMLType.Q5_K,
            'Q6_K': GGMLType.Q6_K,
            'Q8_K': GGMLType.Q8_K,
        }
        
        ggml_type = type_map.get(ftype.upper(), GGMLType.Q4_0)
        return GGML_TYPE_SIZES.get(ggml_type, 0.625)
    
    def _estimate_weights(self, n_embd: int, n_layer: int, type_size: float, architecture: str) -> int:
        """
        Estimate weight memory based on architecture.
        
        Args:
            n_embd: Embedding dimension
            n_layer: Number of layers
            type_size: Bytes per element
            architecture: Model architecture
            
        Returns:
            Weight memory in bytes
        """
        # Base transformer weights per layer:
        # - Attention: 4 * n_embd * n_embd (Q, K, V, O projections)
        # - MLP: 8 * n_embd * n_embd (up, down, gate for some archs)
        
        per_layer = (
            4 * n_embd * n_embd * type_size +  # Attention
            8 * n_embd * n_embd * type_size    # MLP (generous estimate)
        )
        
        total_weights = n_layer * per_layer
        
        # Architecture-specific adjustments
        if architecture in ['mixtral', 'qwen2moe']:
            # MoE models have more parameters
            total_weights *= 2.5
        elif architecture == 'falcon':
            # Falcon has different structure
            total_weights *= 1.2
        
        return int(total_weights)
    
    def _estimate_params_from_size(self, size_gb: float, architecture: str, ftype: str) -> ModelParams:
        """
        Estimate model parameters from file size.
        
        Args:
            size_gb: File size in GB
            architecture: Model architecture
            ftype: Quantization type
            
        Returns:
            ModelParams with estimated values
        """
        # Rough estimates based on common models
        if size_gb < 2:
            # 1B-2B models
            return ModelParams(
                n_vocab=32000,
                n_ctx=2048,
                n_embd=2048,
                n_head=16,
                n_layer=22,
                ftype=ftype,
                architecture=architecture
            )
        elif size_gb < 5:
            # 7B models
            return ModelParams(
                n_vocab=32000,
                n_ctx=4096,
                n_embd=4096,
                n_head=32,
                n_layer=32,
                ftype=ftype,
                architecture=architecture
            )
        elif size_gb < 10:
            # 13B models
            return ModelParams(
                n_vocab=32000,
                n_ctx=4096,
                n_embd=5120,
                n_head=40,
                n_layer=40,
                ftype=ftype,
                architecture=architecture
            )
        elif size_gb < 25:
            # 30B-34B models
            return ModelParams(
                n_vocab=32000,
                n_ctx=4096,
                n_embd=6656,
                n_head=52,
                n_layer=48,
                ftype=ftype,
                architecture=architecture
            )
        else:
            # 70B+ models
            return ModelParams(
                n_vocab=32000,
                n_ctx=4096,
                n_embd=8192,
                n_head=64,
                n_layer=80,
                ftype=ftype,
                architecture=architecture
            )


def estimate_model_memory(
    n_vocab: int = 32000,
    n_ctx: int = 2048,
    n_embd: int = 4096,
    n_layer: int = 32,
    ftype: str = "Q4_0"
) -> Dict[str, float]:
    """
    Convenience function for quick memory estimation.
    
    Args:
        n_vocab: Vocabulary size
        n_ctx: Context window
        n_embd: Embedding dimension
        n_layer: Number of layers
        ftype: Quantization type
        
    Returns:
        Dictionary with memory breakdown in MB
    """
    estimator = MemoryEstimator()
    estimate = estimator.estimate_from_params(n_vocab, n_ctx, n_embd, n_layer, ftype)
    
    return {
        'embeddings_mb': estimate.embeddings_mb,
        'kv_cache_mb': estimate.kv_cache_mb,
        'weights_mb': estimate.weights_mb,
        'overhead_mb': estimate.overhead_mb,
        'total_mb': estimate.total_mb,
        'total_gb': estimate.total_gb
    }


if __name__ == "__main__":
    print("=== Memory Estimation Test ===\n")
    
    estimator = MemoryEstimator()
    
    # Test different model configurations
    test_configs = [
        ("Llama 2B Q4_0", 32000, 2048, 2048, 22, "Q4_0"),
        ("Llama 7B Q4_0", 32000, 4096, 4096, 32, "Q4_0"),
        ("Llama 13B Q4_0", 32000, 4096, 5120, 40, "Q4_0"),
        ("Llama 70B Q4_0", 32000, 4096, 8192, 80, "Q4_0"),
        ("Llama 7B Q8_0", 32000, 4096, 4096, 32, "Q8_0"),
        ("Llama 7B F16", 32000, 4096, 4096, 32, "F16"),
    ]
    
    for name, n_vocab, n_ctx, n_embd, n_layer, ftype in test_configs:
        estimate = estimator.estimate_from_params(n_vocab, n_ctx, n_embd, n_layer, ftype)
        print(f"{name}:")
        print(f"  Total: {estimate.total_gb:.2f} GB ({estimate.total_mb:.0f} MB)")
        print(f"  Breakdown:")
        print(f"    Embeddings: {estimate.embeddings_mb:.0f} MB")
        print(f"    KV Cache: {estimate.kv_cache_mb:.0f} MB")
        print(f"    Weights: {estimate.weights_mb:.0f} MB")
        print(f"    Overhead: {estimate.overhead_mb:.0f} MB")
        print()
