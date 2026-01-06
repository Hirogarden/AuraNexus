"""
Smart Layer Splitting and Offloading Strategies
Based on KoboldCPP's intelligent layer placement patterns
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from enum import Enum


class LayerType(Enum):
    """Types of layers in transformer models."""
    EMBEDDING = "embedding"
    ATTENTION = "attention"
    MLP = "mlp"
    NORM = "norm"
    OUTPUT = "output"


class OffloadStrategy(Enum):
    """Layer offloading strategies for different scenarios."""
    ALL = "all"                      # Offload everything (high VRAM)
    ATTENTION_ONLY = "attention"     # Offload attention layers only
    MLP_PRIORITY = "mlp"            # Prioritize MLP layers (MoE models)
    SEQUENTIAL = "sequential"        # Sequential from bottom up
    ALTERNATING = "alternating"      # Alternate attention/MLP
    NONE = "none"                    # CPU only


@dataclass
class LayerProfile:
    """Memory profile for a single layer."""
    layer_id: int
    layer_type: LayerType
    size_mb: float
    compute_intensity: float  # Higher = more compute benefit from GPU
    memory_bandwidth: float   # Higher = more bandwidth benefit from GPU
    
    def offload_priority(self) -> float:
        """Calculate offload priority score (higher = offload first)."""
        # Weight compute intensity more for attention, memory bandwidth for MLP
        if self.layer_type == LayerType.ATTENTION:
            return self.compute_intensity * 1.5 + self.memory_bandwidth * 0.5
        elif self.layer_type == LayerType.MLP:
            return self.compute_intensity * 0.5 + self.memory_bandwidth * 1.5
        else:
            return self.compute_intensity + self.memory_bandwidth


@dataclass
class SplitConfig:
    """Configuration for layer splitting."""
    total_layers: int
    gpu_layers: int
    offload_strategy: OffloadStrategy
    layer_ids_to_offload: List[int]
    estimated_vram_mb: float
    estimated_speedup: float
    
    def to_modelfile_params(self) -> Dict[str, any]:
        """Convert to Ollama modelfile parameters."""
        return {
            'num_gpu': self.gpu_layers,
            'main_gpu': 0,  # Primary GPU
        }


class LayerSplitter:
    """
    Intelligent layer splitting for optimal GPU offloading.
    Based on KoboldCPP's sophisticated layer selection.
    """
    
    def __init__(self, vram_available_mb: float):
        """
        Initialize splitter.
        
        Args:
            vram_available_mb: Available VRAM in megabytes
        """
        self.vram_available_mb = vram_available_mb
        self.vram_buffer_mb = 512  # Safety buffer
    
    def profile_model_layers(
        self,
        n_layer: int,
        n_embd: int,
        ftype: str,
        architecture: str = "llama"
    ) -> List[LayerProfile]:
        """
        Profile all layers in a model.
        
        Args:
            n_layer: Number of transformer layers
            n_embd: Embedding dimension
            ftype: Quantization type
            architecture: Model architecture
            
        Returns:
            List of layer profiles
        """
        # Quantization multipliers
        quant_multipliers = {
            'F32': 4.0,
            'F16': 2.0,
            'Q8_0': 1.125,
            'Q6_K': 0.875,
            'Q5_K': 0.75,
            'Q5_0': 0.75,
            'Q4_K': 0.625,
            'Q4_0': 0.625,
            'Q3_K': 0.5,
            'Q2_K': 0.375,
        }
        
        mult = quant_multipliers.get(ftype, 0.625)  # Default to Q4_0
        
        profiles = []
        
        # Embedding layer (input)
        emb_size_mb = (n_embd * 32000 * mult) / (1024 * 1024)  # Typical vocab size
        profiles.append(LayerProfile(
            layer_id=-1,
            layer_type=LayerType.EMBEDDING,
            size_mb=emb_size_mb,
            compute_intensity=0.3,  # Low compute
            memory_bandwidth=0.9    # High bandwidth need
        ))
        
        # Transformer layers
        for i in range(n_layer):
            # Attention layer
            # Q, K, V, O projections: 4 * (n_embd * n_embd)
            attn_size_mb = (4 * n_embd * n_embd * mult) / (1024 * 1024)
            profiles.append(LayerProfile(
                layer_id=i,
                layer_type=LayerType.ATTENTION,
                size_mb=attn_size_mb,
                compute_intensity=0.9,  # High compute (attention is expensive)
                memory_bandwidth=0.6
            ))
            
            # MLP/FFN layer
            # Typically 4x expansion: 2 * (n_embd * 4*n_embd)
            mlp_size_mb = (2 * n_embd * 4 * n_embd * mult) / (1024 * 1024)
            profiles.append(LayerProfile(
                layer_id=i,
                layer_type=LayerType.MLP,
                size_mb=mlp_size_mb,
                compute_intensity=0.7,  # Medium-high compute
                memory_bandwidth=0.8    # High bandwidth (large matrices)
            ))
            
            # Layer norms (small, always include with layer)
            norm_size_mb = (2 * n_embd * mult) / (1024 * 1024)
            profiles.append(LayerProfile(
                layer_id=i,
                layer_type=LayerType.NORM,
                size_mb=norm_size_mb,
                compute_intensity=0.1,
                memory_bandwidth=0.3
            ))
        
        # Output layer
        out_size_mb = (n_embd * 32000 * mult) / (1024 * 1024)
        profiles.append(LayerProfile(
            layer_id=n_layer,
            layer_type=LayerType.OUTPUT,
            size_mb=out_size_mb,
            compute_intensity=0.4,
            memory_bandwidth=0.8
        ))
        
        return profiles
    
    def calculate_split(
        self,
        profiles: List[LayerProfile],
        strategy: OffloadStrategy = OffloadStrategy.SEQUENTIAL
    ) -> SplitConfig:
        """
        Calculate optimal layer split based on strategy.
        
        Args:
            profiles: Layer profiles from profile_model_layers
            strategy: Offloading strategy to use
            
        Returns:
            Split configuration
        """
        usable_vram = self.vram_available_mb - self.vram_buffer_mb
        
        if strategy == OffloadStrategy.NONE:
            return SplitConfig(
                total_layers=len([p for p in profiles if p.layer_type in {LayerType.ATTENTION, LayerType.MLP}]) // 2,
                gpu_layers=0,
                offload_strategy=strategy,
                layer_ids_to_offload=[],
                estimated_vram_mb=0,
                estimated_speedup=1.0
            )
        
        # Get transformer layers only (exclude embedding/output)
        transformer_layers = [p for p in profiles if p.layer_id >= 0 and p.layer_id < max(p.layer_id for p in profiles if p.layer_type != LayerType.OUTPUT)]
        n_layers = len(set(p.layer_id for p in transformer_layers))
        
        if strategy == OffloadStrategy.ALL:
            # Try to fit everything
            total_size = sum(p.size_mb for p in profiles)
            if total_size <= usable_vram:
                return SplitConfig(
                    total_layers=n_layers,
                    gpu_layers=-1,  # Ollama uses -1 for "all layers"
                    offload_strategy=strategy,
                    layer_ids_to_offload=list(range(n_layers)),
                    estimated_vram_mb=total_size,
                    estimated_speedup=3.0  # Full GPU
                )
            else:
                # Fall back to sequential
                strategy = OffloadStrategy.SEQUENTIAL
        
        if strategy == OffloadStrategy.SEQUENTIAL:
            # Offload layers from bottom up until VRAM full
            accumulated_mb = 0
            offloaded_layers = []
            
            for layer_id in range(n_layers):
                # Get all components of this layer
                layer_components = [p for p in profiles if p.layer_id == layer_id]
                layer_size = sum(p.size_mb for p in layer_components)
                
                if accumulated_mb + layer_size <= usable_vram:
                    accumulated_mb += layer_size
                    offloaded_layers.append(layer_id)
                else:
                    break
            
            return SplitConfig(
                total_layers=n_layers,
                gpu_layers=len(offloaded_layers),
                offload_strategy=strategy,
                layer_ids_to_offload=offloaded_layers,
                estimated_vram_mb=accumulated_mb,
                estimated_speedup=1.5 + (len(offloaded_layers) / n_layers) * 1.5
            )
        
        elif strategy == OffloadStrategy.ATTENTION_ONLY:
            # Offload only attention layers (better for memory-limited scenarios)
            accumulated_mb = 0
            offloaded_layers = []
            
            # Sort attention layers by priority
            attn_profiles = [p for p in profiles if p.layer_type == LayerType.ATTENTION]
            attn_profiles.sort(key=lambda p: p.offload_priority(), reverse=True)
            
            for profile in attn_profiles:
                if accumulated_mb + profile.size_mb <= usable_vram:
                    accumulated_mb += profile.size_mb
                    if profile.layer_id not in offloaded_layers:
                        offloaded_layers.append(profile.layer_id)
            
            return SplitConfig(
                total_layers=n_layers,
                gpu_layers=len(offloaded_layers),
                offload_strategy=strategy,
                layer_ids_to_offload=sorted(offloaded_layers),
                estimated_vram_mb=accumulated_mb,
                estimated_speedup=1.3 + (len(offloaded_layers) / n_layers) * 0.8
            )
        
        elif strategy == OffloadStrategy.MLP_PRIORITY:
            # Prioritize MLP layers (good for MoE models)
            accumulated_mb = 0
            offloaded_layers = []
            
            # Sort MLP layers by priority
            mlp_profiles = [p for p in profiles if p.layer_type == LayerType.MLP]
            mlp_profiles.sort(key=lambda p: p.offload_priority(), reverse=True)
            
            for profile in mlp_profiles:
                if accumulated_mb + profile.size_mb <= usable_vram:
                    accumulated_mb += profile.size_mb
                    if profile.layer_id not in offloaded_layers:
                        offloaded_layers.append(profile.layer_id)
            
            return SplitConfig(
                total_layers=n_layers,
                gpu_layers=len(offloaded_layers),
                offload_strategy=strategy,
                layer_ids_to_offload=sorted(offloaded_layers),
                estimated_vram_mb=accumulated_mb,
                estimated_speedup=1.4 + (len(offloaded_layers) / n_layers) * 1.0
            )
        
        elif strategy == OffloadStrategy.ALTERNATING:
            # Alternate attention and MLP layers
            accumulated_mb = 0
            offloaded_layers = []
            
            # Alternate between attention and MLP
            for layer_id in range(n_layers):
                # Get attention or MLP components alternating
                layer_type = LayerType.ATTENTION if layer_id % 2 == 0 else LayerType.MLP
                layer_components = [p for p in profiles if p.layer_id == layer_id and p.layer_type == layer_type]
                layer_size = sum(p.size_mb for p in layer_components)
                
                if accumulated_mb + layer_size <= usable_vram:
                    accumulated_mb += layer_size
                    if layer_id not in offloaded_layers:
                        offloaded_layers.append(layer_id)
                else:
                    break
            
            return SplitConfig(
                total_layers=n_layers,
                gpu_layers=len(offloaded_layers),
                offload_strategy=strategy,
                layer_ids_to_offload=sorted(offloaded_layers),
                estimated_vram_mb=accumulated_mb,
                estimated_speedup=1.6 + (len(offloaded_layers) / n_layers) * 1.2
            )
        
        # Default to sequential
        return self.calculate_split(profiles, OffloadStrategy.SEQUENTIAL)
    
    def recommend_strategy(
        self,
        architecture: str,
        is_moe: bool = False,
        is_rnn: bool = False
    ) -> OffloadStrategy:
        """
        Recommend offloading strategy based on model characteristics.
        
        Args:
            architecture: Model architecture name
            is_moe: Is this a Mixture of Experts model?
            is_rnn: Is this an RNN-style model?
            
        Returns:
            Recommended offloading strategy
        """
        # RNN-style models benefit from sequential
        if is_rnn:
            return OffloadStrategy.SEQUENTIAL
        
        # MoE models should prioritize MLP (where experts are)
        if is_moe:
            return OffloadStrategy.MLP_PRIORITY
        
        # High VRAM: offload everything
        if self.vram_available_mb > 12000:  # >12GB
            return OffloadStrategy.ALL
        
        # Medium VRAM: sequential is safe
        elif self.vram_available_mb > 6000:  # 6-12GB
            return OffloadStrategy.SEQUENTIAL
        
        # Low VRAM: attention only (most compute benefit per MB)
        else:  # <6GB
            return OffloadStrategy.ATTENTION_ONLY


def get_optimal_split(
    n_layer: int,
    n_embd: int,
    ftype: str,
    vram_available_mb: float,
    architecture: str = "llama",
    is_moe: bool = False,
    is_rnn: bool = False
) -> SplitConfig:
    """
    Convenience function to get optimal split configuration.
    
    Args:
        n_layer: Number of layers
        n_embd: Embedding dimension
        ftype: Quantization type
        vram_available_mb: Available VRAM in MB
        architecture: Model architecture
        is_moe: Is MoE model
        is_rnn: Is RNN-style model
        
    Returns:
        Optimal split configuration
    """
    splitter = LayerSplitter(vram_available_mb)
    profiles = splitter.profile_model_layers(n_layer, n_embd, ftype, architecture)
    strategy = splitter.recommend_strategy(architecture, is_moe, is_rnn)
    return splitter.calculate_split(profiles, strategy)


# Example usage
if __name__ == "__main__":
    print("Smart Layer Splitting Demo")
    print("=" * 60)
    
    # Test with 8GB VRAM (like RTX 5060)
    vram_mb = 7810  # 8151 MB total - some used by system
    
    test_models = [
        ("Llama 2B Q4_0", 22, 2048, "Q4_0", False, False),
        ("Llama 7B Q4_0", 32, 4096, "Q4_0", False, False),
        ("Mixtral 8x7B Q4_0", 32, 4096, "Q4_0", True, False),
        ("Mamba 2.8B", 64, 2560, "Q4_0", False, True),
    ]
    
    for name, n_layer, n_embd, ftype, is_moe, is_rnn in test_models:
        print(f"\n{name}:")
        print("-" * 60)
        
        config = get_optimal_split(n_layer, n_embd, ftype, vram_mb, is_moe=is_moe, is_rnn=is_rnn)
        
        print(f"Strategy: {config.offload_strategy.value}")
        print(f"GPU Layers: {config.gpu_layers}/{config.total_layers}")
        print(f"VRAM Usage: {config.estimated_vram_mb:.0f} MB")
        print(f"Estimated Speedup: {config.estimated_speedup:.1f}x")
        print(f"Layers to offload: {config.layer_ids_to_offload[:5]}{'...' if len(config.layer_ids_to_offload) > 5 else ''}")
