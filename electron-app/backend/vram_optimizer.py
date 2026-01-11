"""
VRAM Optimization Utilities for Low VRAM Scenarios

Provides automatic detection and optimization for NVIDIA GPUs with limited VRAM.
Based on patterns from KoboldCPP GGUF handling.

Author: AuraNexus
Created: 2024
"""

import subprocess
import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

try:
    from memory_estimator import MemoryEstimator, MemoryEstimate
    MEMORY_ESTIMATOR_AVAILABLE = True
except ImportError:
    MEMORY_ESTIMATOR_AVAILABLE = False
    MemoryEstimator = None
    MemoryEstimate = None


@dataclass
class VRAMInfo:
    """VRAM usage information."""
    total_mb: float
    used_mb: float
    free_mb: float
    used_percent: float


@dataclass
class ModelOptimizationParams:
    """Optimized parameters for model loading."""
    gpu_layers: int
    n_batch: int
    n_ctx: int
    offload_kqv: bool
    use_mmap: bool
    low_vram_mode: bool
    reason: str


class VRAMMonitor:
    """Monitor NVIDIA GPU VRAM usage."""
    
    def __init__(self):
        """Initialize VRAM monitor."""
        self.total_vram_mb = self._get_total_vram()
        self.gpu_available = self.total_vram_mb > 0
    
    def _get_total_vram(self) -> float:
        """
        Get total VRAM in MB.
        
        Returns:
            Total VRAM in megabytes, or 0 if nvidia-smi not available
        """
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass
        return 0.0  # No NVIDIA GPU or nvidia-smi not available
    
    def get_current_usage(self) -> VRAMInfo:
        """
        Get current VRAM usage.
        
        Returns:
            VRAMInfo with current usage statistics
        """
        if not self.gpu_available:
            return VRAMInfo(
                total_mb=0,
                used_mb=0,
                free_mb=0,
                used_percent=0
            )
        
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used,memory.free',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                used, free = map(float, result.stdout.strip().split(','))
                
                return VRAMInfo(
                    total_mb=self.total_vram_mb,
                    used_mb=used,
                    free_mb=free,
                    used_percent=(used / self.total_vram_mb * 100) if self.total_vram_mb > 0 else 0
                )
        except (subprocess.TimeoutExpired, ValueError, AttributeError):
            pass
        
        # Fallback
        return VRAMInfo(
            total_mb=self.total_vram_mb,
            used_mb=0,
            free_mb=self.total_vram_mb,
            used_percent=0
        )
    
    def can_fit_model(self, model_size_mb: float) -> Tuple[bool, str]:
        """
        Check if model can fit in available VRAM.
        
        Args:
            model_size_mb: Model size in megabytes
            
        Returns:
            Tuple of (can_fit, message)
        """
        if not self.gpu_available:
            return False, "No NVIDIA GPU detected"
        
        usage = self.get_current_usage()
        free_mb = usage.free_mb
        
        # Need 20% buffer for operations
        required_mb = model_size_mb * 1.2
        
        if required_mb <= free_mb:
            return True, f"Model fits: {required_mb:.0f}MB needed, {free_mb:.0f}MB available"
        else:
            # Calculate how many layers could fit
            layers_possible = int((free_mb / required_mb) * 32)  # Assume 32 layers baseline
            return False, f"Only ~{layers_possible} layers can fit (need {required_mb:.0f}MB, have {free_mb:.0f}MB)"
    
    def get_vram_summary(self) -> str:
        """
        Get human-readable VRAM summary.
        
        Returns:
            Formatted VRAM status string
        """
        if not self.gpu_available:
            return "No NVIDIA GPU detected (CPU-only mode)"
        
        usage = self.get_current_usage()
        return (
            f"VRAM: {usage.used_mb:.0f}MB / {usage.total_mb:.0f}MB used "
            f"({usage.used_percent:.1f}%) | {usage.free_mb:.0f}MB free"
        )


class LowVRAMOptimizer:
    """
    Optimize model loading parameters for low VRAM scenarios.
    
    Based on KoboldCPP patterns for efficient GGUF model loading.
    """
    
    # VRAM thresholds in GB
    VRAM_THRESHOLD_LOW = 8.0      # Below this is considered low VRAM
    VRAM_THRESHOLD_VERY_LOW = 6.0 # Below this is very constrained
    
    def __init__(self, vram_gb: Optional[float] = None):
        """
        Initialize optimizer.
        
        Args:
            vram_gb: Total VRAM in GB. If None, auto-detect.
        """
        if vram_gb is None:
            monitor = VRAMMonitor()
            vram_gb = monitor.total_vram_mb / 1024 if monitor.gpu_available else 0
        
        self.vram_gb = vram_gb
        self.is_low_vram = vram_gb <= self.VRAM_THRESHOLD_LOW
        self.is_very_low_vram = vram_gb <= self.VRAM_THRESHOLD_VERY_LOW
        
        # Initialize memory estimator if available
        if MEMORY_ESTIMATOR_AVAILABLE:
            self.memory_estimator = MemoryEstimator()
        else:
            self.memory_estimator = None
    
    def estimate_model_layers(self, model_size_gb: float) -> int:
        """
        Estimate how many layers can fit in VRAM.
        
        Args:
            model_size_gb: Model size in gigabytes
            
        Returns:
            Estimated number of layers that can be offloaded to GPU
        """
        if self.vram_gb == 0:
            return 0  # CPU-only
        
        # If memory estimator is available, use it for better accuracy
        if self.memory_estimator and MEMORY_ESTIMATOR_AVAILABLE:
            return self._estimate_layers_with_memory_calc(model_size_gb)
        
        # Fallback to simple ratio calculation
        # Reserve VRAM for OS and other processes
        usable_vram_gb = self.vram_gb * 0.7  # Use 70% of available VRAM
        
        # Estimate layers (assuming typical 32-layer model)
        # This is a rough approximation
        if model_size_gb <= 0:
            return 0
        
        ratio = usable_vram_gb / model_size_gb
        estimated_layers = int(ratio * 32)
        
        # Apply caps based on VRAM tier
        if self.is_very_low_vram:
            estimated_layers = min(estimated_layers, 12)  # Cap at 12 layers
        elif self.is_low_vram:
            estimated_layers = min(estimated_layers, 20)  # Cap at 20 layers
        
        return max(0, estimated_layers)
    
    def _estimate_layers_with_memory_calc(self, model_size_gb: float) -> int:
        """
        Estimate layers using detailed memory calculations.
        
        Args:
            model_size_gb: Model size in GB
            
        Returns:
            Estimated layers that fit in VRAM
        """
        # Determine model parameters from size
        if model_size_gb < 2:
            n_embd, n_layer = 2048, 22
        elif model_size_gb < 5:
            n_embd, n_layer = 4096, 32
        elif model_size_gb < 10:
            n_embd, n_layer = 5120, 40
        else:
            n_embd, n_layer = 8192, 80
        
        # Calculate memory per layer
        mem_estimate = self.memory_estimator.estimate_from_params(
            n_vocab=32000,
            n_ctx=4096,
            n_embd=n_embd,
            n_layer=n_layer,
            ftype="Q4_0"
        )
        
        # Get usable VRAM
        usable_vram_mb = self.vram_gb * 1024 * 0.7  # 70% usable
        
        # Weights are the part that gets offloaded
        weight_mb_per_layer = mem_estimate.weights_mb / n_layer
        
        # Calculate how many layers fit
        layers_that_fit = int(usable_vram_mb / weight_mb_per_layer)
        
        # Apply tier-based caps
        if self.is_very_low_vram:
            layers_that_fit = min(layers_that_fit, 12)
        elif self.is_low_vram:
            layers_that_fit = min(layers_that_fit, 20)
        
        return max(0, min(layers_that_fit, n_layer))
    
    def get_optimal_params(
        self,
        model_size_gb: float,
        user_preference: Optional[Dict] = None
    ) -> ModelOptimizationParams:
        """
        Get optimal parameters for model loading.
        
        Args:
            model_size_gb: Model size in gigabytes
            user_preference: Optional user preference overrides
            
        Returns:
            ModelOptimizationParams with optimized settings
        """
        user_preference = user_preference or {}
        
        # CPU-only fallback
        if self.vram_gb == 0:
            return ModelOptimizationParams(
                gpu_layers=0,
                n_batch=128,
                n_ctx=2048,
                offload_kqv=False,
                use_mmap=True,
                low_vram_mode=True,
                reason="No GPU detected - CPU-only mode"
            )
        
        # High VRAM - no restrictions
        if not self.is_low_vram:
            return ModelOptimizationParams(
                gpu_layers=user_preference.get('gpu_layers', -1),  # All layers
                n_batch=user_preference.get('n_batch', 512),
                n_ctx=user_preference.get('n_ctx', 8192),
                offload_kqv=True,
                use_mmap=True,
                low_vram_mode=False,
                reason=f"High VRAM ({self.vram_gb:.1f}GB) - full GPU acceleration"
            )
        
        # Low VRAM optimization
        estimated_layers = self.estimate_model_layers(model_size_gb)
        
        # Very low VRAM - aggressive optimization
        if self.is_very_low_vram:
            return ModelOptimizationParams(
                gpu_layers=user_preference.get('gpu_layers', min(estimated_layers, 12)),
                n_batch=user_preference.get('n_batch', 128),
                n_ctx=user_preference.get('n_ctx', 4096),
                offload_kqv=False,  # Keep KV cache on CPU
                use_mmap=True,      # Use memory mapping
                low_vram_mode=True,
                reason=f"Very low VRAM ({self.vram_gb:.1f}GB) - aggressive optimization, ~{estimated_layers} layers"
            )
        
        # Low VRAM - moderate optimization
        return ModelOptimizationParams(
            gpu_layers=user_preference.get('gpu_layers', min(estimated_layers, 20)),
            n_batch=user_preference.get('n_batch', 256),
            n_ctx=user_preference.get('n_ctx', 4096),
            offload_kqv=False,  # Keep KV cache on CPU
            use_mmap=True,
            low_vram_mode=True,
            reason=f"Low VRAM ({self.vram_gb:.1f}GB) - optimized for efficiency, ~{estimated_layers} layers"
        )
    
    def generate_modelfile_params(self, params: ModelOptimizationParams) -> str:
        """
        Generate Ollama modelfile parameters from optimization params.
        
        Args:
            params: ModelOptimizationParams to convert
            
        Returns:
            Modelfile parameter string
        """
        lines = []
        
        if params.gpu_layers > 0:
            lines.append(f"PARAMETER num_gpu {params.gpu_layers}")
        
        lines.append(f"PARAMETER num_batch {params.n_batch}")
        lines.append(f"PARAMETER num_ctx {params.n_ctx}")
        
        if params.use_mmap:
            lines.append("PARAMETER mmap true")
        
        return "\n".join(lines)
    
    def should_optimize_model(self, model_size_gb: float) -> bool:
        """
        Determine if model needs optimization.
        
        Args:
            model_size_gb: Model size in gigabytes
            
        Returns:
            True if optimization recommended
        """
        if not self.is_low_vram:
            return False
        
        # If model is more than 50% of VRAM, optimize
        return model_size_gb > (self.vram_gb * 0.5)


def get_system_vram_info() -> Dict[str, any]:
    """
    Get comprehensive VRAM information for the system.
    
    Returns:
        Dictionary with VRAM details and recommendations
    """
    monitor = VRAMMonitor()
    
    if not monitor.gpu_available:
        return {
            'gpu_available': False,
            'total_vram_gb': 0,
            'recommendation': 'CPU-only mode',
            'vram_tier': 'none'
        }
    
    usage = monitor.get_current_usage()
    total_gb = usage.total_mb / 1024
    
    # Determine VRAM tier
    if total_gb >= 16:
        tier = 'high'
        recommendation = 'Full GPU acceleration available'
    elif total_gb >= 8:
        tier = 'medium'
        recommendation = 'Low VRAM optimizations recommended'
    elif total_gb >= 6:
        tier = 'low'
        recommendation = 'Aggressive optimizations required'
    else:
        tier = 'very_low'
        recommendation = 'Use small/quantized models only'
    
    return {
        'gpu_available': True,
        'total_vram_gb': total_gb,
        'total_vram_mb': usage.total_mb,
        'used_vram_mb': usage.used_mb,
        'free_vram_mb': usage.free_mb,
        'used_percent': usage.used_percent,
        'vram_tier': tier,
        'recommendation': recommendation,
        'summary': monitor.get_vram_summary()
    }


# Convenience function for quick checks
def quick_vram_check() -> str:
    """
    Quick VRAM status check.
    
    Returns:
        Human-readable VRAM status
    """
    monitor = VRAMMonitor()
    return monitor.get_vram_summary()


if __name__ == "__main__":
    # Test the VRAM monitoring
    print("=== VRAM Optimization Utilities Test ===\n")
    
    # System info
    info = get_system_vram_info()
    print("System VRAM Info:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    print("\n" + "="*50 + "\n")
    
    # Test optimizer
    optimizer = LowVRAMOptimizer()
    
    # Test with different model sizes
    test_models = [
        ("Small 2B Q4", 1.5),
        ("Medium 7B Q4", 4.0),
        ("Large 13B Q4", 7.5),
        ("XL 70B Q4", 38.0),
    ]
    
    print("Optimization Recommendations:\n")
    for name, size_gb in test_models:
        params = optimizer.get_optimal_params(size_gb)
        print(f"{name} ({size_gb}GB):")
        print(f"  GPU Layers: {params.gpu_layers}")
        print(f"  Batch Size: {params.n_batch}")
        print(f"  Context: {params.n_ctx}")
        print(f"  Low VRAM Mode: {params.low_vram_mode}")
        print(f"  Reason: {params.reason}")
        print()
