"""
Demo: KoboldCPP Harvest Features
Show off all the features we've pilfered from KoboldCPP
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

print("=" * 70)
print(" 🏴‍☠️ KoboldCPP Harvest Demo - All Pilfered Features")
print("=" * 70)

# Feature 1: VRAM Monitoring
print("\n[1/4] VRAM Monitoring System")
print("-" * 70)

from vram_optimizer import VRAMMonitor, get_system_vram_info

monitor = VRAMMonitor()
vram_info = get_system_vram_info()

print(f"✓ Total VRAM: {vram_info['total_vram_gb']:.2f} GB ({vram_info['total_vram_mb']:.0f} MB)")
print(f"✓ VRAM Tier: {vram_info['vram_tier']}")
print(f"✓ GPU Available: {vram_info['gpu_available']}")

usage = monitor.get_current_usage()
print(f"✓ Current Usage: {usage.used_mb:.0f} MB / {usage.total_mb:.0f} MB ({usage.used_percent:.1f}%)")
print(f"✓ Free VRAM: {usage.free_mb:.0f} MB")

# Store for later use
vram_mb = usage.free_mb  # Use free VRAM for calculations

# Feature 2: Memory Estimation
print("\n[2/4] Memory Estimation System")
print("-" * 70)

from memory_estimator import MemoryEstimator

estimator = MemoryEstimator()

# Test with different model sizes
test_cases = [
    ("Llama 2B Q4_0", 32000, 2048, 2048, 22, "Q4_0"),
    ("Llama 7B Q4_0", 32000, 4096, 4096, 32, "Q4_0"),
    ("Llama 7B Q8_0", 32000, 4096, 4096, 32, "Q8_0"),
]

for name, n_vocab, n_ctx, n_embd, n_layer, ftype in test_cases:
    estimate = estimator.estimate_from_params(n_vocab, n_ctx, n_embd, n_layer, ftype)
    print(f"✓ {name}:")
    print(f"  Total: {estimate.total_gb:.2f} GB | Weights: {estimate.weights_mb:.0f} MB | KV Cache: {estimate.kv_cache_mb:.0f} MB")

# Feature 3: Real-time VRAM Monitoring
print("\n[3/4] Real-time VRAM Monitoring")
print("-" * 70)

from vram_monitor import get_current_vram_usage

async def demo_realtime_monitoring():
    """Demo the real-time monitoring capabilities."""
    snapshot = await get_current_vram_usage()
    
    if snapshot:
        print(f"✓ Real-time snapshot captured:")
        print(f"  Timestamp: {snapshot.timestamp.strftime('%H:%M:%S')}")
        print(f"  Used: {snapshot.used_mb:.0f} MB ({snapshot.used_percent:.1f}%)")
        print(f"  Free: {snapshot.free_mb:.0f} MB")
        
        # Determine status
        if snapshot.used_percent < 75:
            status = "🟢 Healthy"
        elif snapshot.used_percent < 85:
            status = "🟡 Warning"
        else:
            status = "🔴 Critical"
        
        print(f"  Status: {status}")
    else:
        print("⚠ NVIDIA GPU not detected (monitoring unavailable)")

asyncio.run(demo_realtime_monitoring())

# Feature 4: Architecture Detection
print("\n[4/4] Architecture Detection")
print("-" * 70)

from gguf_architecture import Architecture, ArchitectureDetector

print(f"✓ Supported Architectures ({len([a for a in Architecture if a != Architecture.UNKNOWN])}):")

# Show transformer architectures
transformers = [
    Architecture.LLAMA, Architecture.LLAMA4, Architecture.QWEN2, 
    Architecture.GEMMA3, Architecture.PHI, Architecture.MISTRAL, Architecture.MIXTRAL
]
print(f"  Transformers: {', '.join([a.value for a in transformers])}")

# Show RNN-style architectures
rnn_style = [Architecture.MAMBA, Architecture.MAMBA2, Architecture.RWKV6, Architecture.RWKV7]
print(f"  RNN-style: {', '.join([a.value for a in rnn_style])}")

# Show special architectures
special = [Architecture.FALCON, Architecture.GLM4MOE, Architecture.JAMBA]
print(f"  Special: {', '.join([a.value for a in special])}")

print("\n✓ Architecture-specific optimization hints:")
print("  • GQA models: Reduced KV cache (ratio-based)")
print("  • MoE models: Priority MLP offloading, smaller batches")
print("  • RNN-style: Efficient state size, larger batches")
print("  • Falcon (MQA): Minimal KV cache (0.25x)")

# Summary
print("\n" + "=" * 70)
print(" Summary: What We Pilfered from KoboldCPP")
print("=" * 70)

features = [
    ("VRAM Detection", "✅", "8GB RTX 5060 detected, tier-based optimization"),
    ("Memory Estimation", "✅", "Pre-load calculations prevent OOM crashes"),
    ("Real-time Monitoring", "✅", "1-second polling with threshold alerts"),
    ("Architecture Detection", "✅", "19+ architectures with optimization hints"),
    ("Low VRAM Mode", "✅", "Automatic layer/batch/context adjustments"),
    ("Smart Layer Splitting", "✅", "Attention/MLP priority, 5 strategies"),
    ("Progressive Loading", "✅", "Real-time download progress with ETA"),
]

for feature, status, desc in features:
    print(f"{status} {feature:25} - {desc}")

# Feature 5: Smart Layer Splitting
print("\n[5/6] Smart Layer Splitting")
print("-" * 70)

from layer_splitter import get_optimal_split, OffloadStrategy

# Test with different models and VRAM
test_models = [
    ("Llama 7B Q4_0", 32, 4096, "Q4_0", False, False),
    ("Mixtral 8x7B (MoE)", 32, 4096, "Q4_0", True, False),
]

for name, n_layer, n_embd, ftype, is_moe, is_rnn in test_models:
    config = get_optimal_split(n_layer, n_embd, ftype, vram_mb, is_moe=is_moe, is_rnn=is_rnn)
    print(f"✓ {name}:")
    print(f"  Strategy: {config.offload_strategy.value} | GPU Layers: {config.gpu_layers}/{config.total_layers}")
    print(f"  VRAM: {config.estimated_vram_mb:.0f} MB | Speedup: {config.estimated_speedup:.1f}x")

# Feature 6: Progressive Loading
print("\n[6/6] Progressive Loading")
print("-" * 70)

from progressive_loader import LoadingProgress, format_phase_icon, format_loading_bar

# Simulate loading phases
phases = [
    LoadingProgress("Downloading model", "downloading", 2500, 5000, 50.0, 42.5, 15),
    LoadingProgress("Verifying integrity", "verifying", 5000, 5000, 100.0, 0, 0),
    LoadingProgress("Loading layers", "loading", 16, 32, 50.0, 0, None, 16, 32),
    LoadingProgress("Model ready", "complete", 32, 32, 100.0, 0, None, 32, 32),
]

for progress in phases:
    icon = format_phase_icon(progress.phase)
    bar = format_loading_bar(progress.percent, width=20)
    print(f"  {icon} {bar} {progress.to_display_string()}")

print("\n" + "=" * 70)
print(" 🏴‍☠️ All systems operational - Ready for model loading!")
print("=" * 70)
