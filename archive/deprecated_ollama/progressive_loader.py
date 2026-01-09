"""
Progressive Model Loading with Real-time Feedback
Based on KoboldCPP's tensor-by-tensor loading progress
"""

from dataclasses import dataclass
from typing import Optional, Callable, AsyncIterator
from datetime import datetime
import asyncio


@dataclass
class LoadingProgress:
    """Progress information for model loading."""
    status: str                      # Current status message
    phase: str                       # Loading phase (downloading, loading, verifying, etc.)
    completed: int = 0              # Bytes completed
    total: int = 0                  # Total bytes
    percent: float = 0.0            # Percentage complete
    speed_mbps: float = 0.0         # Download/load speed in MB/s
    eta_seconds: Optional[int] = None  # Estimated time remaining
    current_layer: Optional[int] = None  # Current layer being loaded
    total_layers: Optional[int] = None   # Total layers to load
    
    def to_display_string(self) -> str:
        """Convert to human-readable display string."""
        if self.total > 0:
            mb_completed = self.completed / (1024 * 1024)
            mb_total = self.total / (1024 * 1024)
            
            parts = [
                f"{self.status}",
                f"{self.percent:.1f}% ({mb_completed:.1f}/{mb_total:.1f} MB)"
            ]
            
            if self.speed_mbps > 0:
                parts.append(f"@ {self.speed_mbps:.1f} MB/s")
            
            if self.eta_seconds is not None and self.eta_seconds > 0:
                mins, secs = divmod(self.eta_seconds, 60)
                if mins > 0:
                    parts.append(f"ETA: {mins}m {secs}s")
                else:
                    parts.append(f"ETA: {secs}s")
            
            if self.current_layer is not None and self.total_layers is not None:
                parts.append(f"(Layer {self.current_layer}/{self.total_layers})")
            
            return " | ".join(parts)
        else:
            return self.status


class ProgressiveLoader:
    """
    Progressive model loader with detailed feedback.
    Wraps Ollama's pull/create operations with enhanced progress tracking.
    """
    
    def __init__(self, callback: Optional[Callable[[LoadingProgress], None]] = None):
        """
        Initialize progressive loader.
        
        Args:
            callback: Function to call with progress updates
        """
        self.callback = callback
        self._last_update_time = None
        self._last_completed = 0
        self._cancelled = False
    
    def cancel(self):
        """Cancel the loading operation."""
        self._cancelled = True
    
    async def pull_with_progress(
        self,
        client,
        model_name: str
    ) -> AsyncIterator[LoadingProgress]:
        """
        Pull model with detailed progress.
        
        Args:
            client: OllamaClient instance
            model_name: Name of model to pull
            
        Yields:
            LoadingProgress objects
        """
        self._cancelled = False
        self._last_update_time = datetime.now()
        self._last_completed = 0
        
        try:
            async for chunk in client.pull_async(model_name, stream=True):
                if self._cancelled:
                    break
                
                # Parse chunk
                status = chunk.get('status', 'downloading')
                total = chunk.get('total', 0)
                completed = chunk.get('completed', 0)
                
                # Calculate speed
                now = datetime.now()
                time_delta = (now - self._last_update_time).total_seconds()
                speed_mbps = 0.0
                
                if time_delta > 0 and completed > self._last_completed:
                    bytes_delta = completed - self._last_completed
                    speed_mbps = (bytes_delta / time_delta) / (1024 * 1024)
                
                # Calculate ETA
                eta_seconds = None
                if speed_mbps > 0 and total > completed:
                    remaining_bytes = total - completed
                    eta_seconds = int(remaining_bytes / (speed_mbps * 1024 * 1024))
                
                # Determine phase
                phase = "downloading"
                if "verifying" in status.lower():
                    phase = "verifying"
                elif "loading" in status.lower():
                    phase = "loading"
                elif "pulling" in status.lower():
                    phase = "downloading"
                
                progress = LoadingProgress(
                    status=status,
                    phase=phase,
                    completed=completed,
                    total=total,
                    percent=(completed / total * 100) if total > 0 else 0,
                    speed_mbps=speed_mbps,
                    eta_seconds=eta_seconds
                )
                
                # Update tracking
                self._last_update_time = now
                self._last_completed = completed
                
                # Callback
                if self.callback:
                    self.callback(progress)
                
                yield progress
                
        except Exception as e:
            error_progress = LoadingProgress(
                status=f"Error: {str(e)}",
                phase="error",
                percent=0
            )
            if self.callback:
                self.callback(error_progress)
            yield error_progress
    
    async def load_with_progress(
        self,
        client,
        model_name: str
    ) -> AsyncIterator[LoadingProgress]:
        """
        Load model into memory with progress.
        This tracks the actual loading phase after download.
        
        Args:
            client: OllamaClient instance
            model_name: Name of model to load
            
        Yields:
            LoadingProgress objects
        """
        self._cancelled = False
        
        # Initial loading status
        yield LoadingProgress(
            status="Initializing model...",
            phase="init",
            percent=0
        )
        
        # Simulate layer-by-layer loading (Ollama doesn't expose this granularly)
        # In a real implementation, this would hook into the actual loading process
        try:
            # Send a simple request to force model loading
            messages = [{"role": "user", "content": "Hi"}]
            
            async for chunk in client.chat_async(
                model=model_name,
                messages=messages,
                stream=True,
                options={"num_predict": 1}  # Just generate 1 token to trigger load
            ):
                # First response means model is loaded
                yield LoadingProgress(
                    status="Model loaded successfully",
                    phase="complete",
                    percent=100
                )
                break
                
        except Exception as e:
            yield LoadingProgress(
                status=f"Loading failed: {str(e)}",
                phase="error",
                percent=0
            )


def format_phase_icon(phase: str) -> str:
    """Get icon for loading phase."""
    icons = {
        "downloading": "⬇️",
        "verifying": "✓",
        "loading": "⚙️",
        "init": "🔄",
        "complete": "✅",
        "error": "❌"
    }
    return icons.get(phase, "📦")


def format_loading_bar(percent: float, width: int = 30) -> str:
    """
    Create ASCII progress bar.
    
    Args:
        percent: Percentage complete (0-100)
        width: Width of bar in characters
        
    Returns:
        ASCII progress bar string
    """
    filled = int(width * (percent / 100))
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    
    from ollama_client import OllamaClient
    
    async def demo():
        """Demo progressive loading."""
        client = OllamaClient()
        
        def on_progress(progress: LoadingProgress):
            """Progress callback."""
            icon = format_phase_icon(progress.phase)
            bar = format_loading_bar(progress.percent)
            print(f"\r{icon} {bar} {progress.to_display_string()}", end="", flush=True)
        
        loader = ProgressiveLoader(callback=on_progress)
        
        print("Demo: Progressive Model Loading")
        print("=" * 70)
        print("\nNote: This would track actual model pull progress")
        print("For demo, showing progress structure:\n")
        
        # Simulate progress
        phases = [
            ("downloading", 0, 100, 45.2),
            ("downloading", 50, 100, 42.1),
            ("downloading", 100, 100, 38.7),
            ("verifying", 100, 100, 0),
            ("loading", 100, 100, 0),
            ("complete", 100, 100, 0),
        ]
        
        for phase, completed, total, speed in phases:
            progress = LoadingProgress(
                status=f"{phase.capitalize()}...",
                phase=phase,
                completed=completed,
                total=total,
                percent=(completed / total * 100) if total > 0 else 100,
                speed_mbps=speed if speed > 0 else 0
            )
            on_progress(progress)
            await asyncio.sleep(0.5)
        
        print("\n\nDemo complete!")
    
    asyncio.run(demo())
