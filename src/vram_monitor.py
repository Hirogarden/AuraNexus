"""
Real-time VRAM Monitoring System for Ollama Operations
Based on KoboldCPP patterns for continuous GPU memory tracking
"""

import asyncio
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Callable, Dict
from datetime import datetime


@dataclass
class VRAMSnapshot:
    """Snapshot of VRAM state at a moment in time."""
    timestamp: datetime
    total_mb: float
    used_mb: float
    free_mb: float
    used_percent: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'total_mb': self.total_mb,
            'used_mb': self.used_mb,
            'free_mb': self.free_mb,
            'used_percent': self.used_percent
        }


@dataclass
class VRAMThresholds:
    """Thresholds for VRAM usage alerts."""
    warning_percent: float = 80.0  # Yellow alert
    critical_percent: float = 90.0  # Red alert
    oom_buffer_mb: float = 512.0   # Reserve for safety


class VRAMMonitoringSession:
    """
    Real-time VRAM monitoring session.
    Tracks VRAM usage during model operations like inference.
    """
    
    def __init__(
        self,
        poll_interval: float = 1.0,  # Check every second
        thresholds: Optional[VRAMThresholds] = None,
        callback: Optional[Callable[[VRAMSnapshot], None]] = None
    ):
        """
        Initialize monitoring session.
        
        Args:
            poll_interval: How often to check VRAM (seconds)
            thresholds: Alert thresholds
            callback: Function to call with each snapshot
        """
        self.poll_interval = poll_interval
        self.thresholds = thresholds or VRAMThresholds()
        self.callback = callback
        
        self.is_monitoring = False
        self._task: Optional[asyncio.Task] = None
        self._snapshots: list[VRAMSnapshot] = []
        self._peak_usage: float = 0.0
        self._total_vram_mb: Optional[float] = None
        
        # Alert state
        self._warning_triggered = False
        self._critical_triggered = False
    
    async def start(self):
        """Start monitoring VRAM."""
        if self.is_monitoring:
            return
        
        # Get total VRAM first
        self._total_vram_mb = await self._get_total_vram()
        if self._total_vram_mb is None:
            print("Warning: Could not detect NVIDIA GPU, monitoring disabled")
            return
        
        self.is_monitoring = True
        self._task = asyncio.create_task(self._monitoring_loop())
    
    async def stop(self):
        """Stop monitoring VRAM."""
        self.is_monitoring = False
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except asyncio.TimeoutError:
                self._task.cancel()
    
    async def _get_total_vram(self) -> Optional[float]:
        """Get total VRAM capacity."""
        try:
            result = await asyncio.create_subprocess_exec(
                'nvidia-smi',
                '--query-gpu=memory.total',
                '--format=csv,noheader,nounits',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(result.communicate(), timeout=5.0)
            
            if result.returncode == 0:
                return float(stdout.decode().strip())
        except Exception:
            pass
        
        return None
    
    async def _get_vram_snapshot(self) -> Optional[VRAMSnapshot]:
        """Get current VRAM usage snapshot."""
        if self._total_vram_mb is None:
            return None
        
        try:
            result = await asyncio.create_subprocess_exec(
                'nvidia-smi',
                '--query-gpu=memory.used,memory.free',
                '--format=csv,noheader,nounits',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(result.communicate(), timeout=5.0)
            
            if result.returncode == 0:
                used, free = map(float, stdout.decode().strip().split(','))
                used_percent = (used / self._total_vram_mb * 100) if self._total_vram_mb > 0 else 0
                
                return VRAMSnapshot(
                    timestamp=datetime.now(),
                    total_mb=self._total_vram_mb,
                    used_mb=used,
                    free_mb=free,
                    used_percent=used_percent
                )
        except Exception:
            pass
        
        return None
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                snapshot = await self._get_vram_snapshot()
                
                if snapshot:
                    # Track peak usage
                    if snapshot.used_mb > self._peak_usage:
                        self._peak_usage = snapshot.used_mb
                    
                    # Store snapshot
                    self._snapshots.append(snapshot)
                    
                    # Keep only last 100 snapshots
                    if len(self._snapshots) > 100:
                        self._snapshots.pop(0)
                    
                    # Check thresholds
                    await self._check_thresholds(snapshot)
                    
                    # Call callback
                    if self.callback:
                        try:
                            self.callback(snapshot)
                        except Exception as e:
                            print(f"Error in VRAM monitoring callback: {e}")
                
                # Wait for next poll
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"Error in VRAM monitoring loop: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _check_thresholds(self, snapshot: VRAMSnapshot):
        """
        Check if VRAM usage crossed thresholds.
        Based on KoboldCPP's memory pressure detection.
        """
        # Critical threshold (90%+)
        if snapshot.used_percent >= self.thresholds.critical_percent:
            if not self._critical_triggered:
                self._critical_triggered = True
                self._warning_triggered = True  # Implies warning too
                print(f"⚠️  CRITICAL: VRAM at {snapshot.used_percent:.1f}% "
                      f"({snapshot.used_mb:.0f}/{snapshot.total_mb:.0f} MB)")
                print(f"    Free: {snapshot.free_mb:.0f} MB - Consider reducing layers or context")
        
        # Warning threshold (80%+)
        elif snapshot.used_percent >= self.thresholds.warning_percent:
            if not self._warning_triggered:
                self._warning_triggered = True
                print(f"⚠️  WARNING: VRAM at {snapshot.used_percent:.1f}% "
                      f"({snapshot.used_mb:.0f}/{snapshot.total_mb:.0f} MB)")
        
        # Reset if dropped below warning
        elif snapshot.used_percent < self.thresholds.warning_percent - 5:  # 5% hysteresis
            if self._warning_triggered or self._critical_triggered:
                self._warning_triggered = False
                self._critical_triggered = False
                print(f"✓ VRAM usage normalized: {snapshot.used_percent:.1f}%")
    
    def get_current_snapshot(self) -> Optional[VRAMSnapshot]:
        """Get most recent VRAM snapshot."""
        return self._snapshots[-1] if self._snapshots else None
    
    def get_peak_usage_mb(self) -> float:
        """Get peak VRAM usage observed."""
        return self._peak_usage
    
    def get_statistics(self) -> Dict:
        """Get monitoring statistics."""
        if not self._snapshots:
            return {}
        
        used_values = [s.used_mb for s in self._snapshots]
        
        return {
            'peak_mb': self._peak_usage,
            'current_mb': used_values[-1],
            'min_mb': min(used_values),
            'avg_mb': sum(used_values) / len(used_values),
            'sample_count': len(self._snapshots)
        }


class InferenceVRAMTracker:
    """
    Track VRAM during specific inference operations.
    Provides before/after snapshots and delta calculations.
    """
    
    def __init__(self):
        self._session: Optional[VRAMMonitoringSession] = None
        self._before_snapshot: Optional[VRAMSnapshot] = None
        self._during_snapshots: list[VRAMSnapshot] = []
    
    async def __aenter__(self):
        """Start tracking when entering context."""
        # Get baseline snapshot
        temp_session = VRAMMonitoringSession()
        await temp_session.start()
        await asyncio.sleep(0.5)  # Let it get one snapshot
        self._before_snapshot = temp_session.get_current_snapshot()
        await temp_session.stop()
        
        # Start continuous monitoring
        self._session = VRAMMonitoringSession(
            poll_interval=0.5,  # Poll faster during inference
            callback=self._snapshot_callback
        )
        await self._session.start()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop tracking when exiting context."""
        if self._session:
            await self._session.stop()
    
    def _snapshot_callback(self, snapshot: VRAMSnapshot):
        """Store snapshots during tracking."""
        self._during_snapshots.append(snapshot)
    
    def get_vram_delta(self) -> Optional[float]:
        """Get VRAM increase during operation (MB)."""
        if not self._before_snapshot or not self._during_snapshots:
            return None
        
        peak_during = max(s.used_mb for s in self._during_snapshots)
        return peak_during - self._before_snapshot.used_mb
    
    def get_report(self) -> Dict:
        """Get detailed report of VRAM usage during operation."""
        if not self._before_snapshot or not self._during_snapshots:
            return {'status': 'no_data'}
        
        during_used = [s.used_mb for s in self._during_snapshots]
        peak_during = max(during_used)
        delta = peak_during - self._before_snapshot.used_mb
        
        return {
            'status': 'ok',
            'before_mb': self._before_snapshot.used_mb,
            'peak_mb': peak_during,
            'delta_mb': delta,
            'avg_during_mb': sum(during_used) / len(during_used),
            'sample_count': len(self._during_snapshots)
        }


# Convenience function for quick checks
async def get_current_vram_usage() -> Optional[VRAMSnapshot]:
    """
    Get current VRAM usage without starting monitoring session.
    Quick one-shot check.
    """
    try:
        # Get total
        result = await asyncio.create_subprocess_exec(
            'nvidia-smi',
            '--query-gpu=memory.total',
            '--format=csv,noheader,nounits',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=5.0)
        total = float(stdout.decode().strip())
        
        # Get used/free
        result = await asyncio.create_subprocess_exec(
            'nvidia-smi',
            '--query-gpu=memory.used,memory.free',
            '--format=csv,noheader,nounits',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=5.0)
        used, free = map(float, stdout.decode().strip().split(','))
        
        return VRAMSnapshot(
            timestamp=datetime.now(),
            total_mb=total,
            used_mb=used,
            free_mb=free,
            used_percent=(used / total * 100) if total > 0 else 0
        )
    except Exception:
        return None


# Example usage
if __name__ == "__main__":
    async def demo():
        # Quick check
        snapshot = await get_current_vram_usage()
        if snapshot:
            print(f"Current VRAM: {snapshot.used_mb:.0f}/{snapshot.total_mb:.0f} MB "
                  f"({snapshot.used_percent:.1f}%)")
        
        # Continuous monitoring
        print("\nStarting continuous monitoring for 10 seconds...")
        
        def on_snapshot(snap: VRAMSnapshot):
            print(f"  {snap.used_percent:.1f}% - {snap.used_mb:.0f} MB used")
        
        session = VRAMMonitoringSession(
            poll_interval=2.0,
            callback=on_snapshot
        )
        
        await session.start()
        await asyncio.sleep(10)
        await session.stop()
        
        stats = session.get_statistics()
        print(f"\nStatistics:")
        print(f"  Peak: {stats['peak_mb']:.0f} MB")
        print(f"  Average: {stats['avg_mb']:.0f} MB")
        print(f"  Min: {stats['min_mb']:.0f} MB")
    
    asyncio.run(demo())
