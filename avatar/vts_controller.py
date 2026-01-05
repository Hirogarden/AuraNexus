from __future__ import annotations

import json
import threading
import time
from typing import Optional

try:
    import websocket  # websocket-client
except Exception:  # pragma: no cover
    websocket = None


class VTSController:
    """Lean VTube Studio controller stub.

    Connects to VTube Studio WebSocket API on localhost:8001 and can send a
    simple expression/parameter command for testing.
    """

    def __init__(self, url: str = "ws://localhost:8001") -> None:
        self.url = url
        self.ws: Optional["websocket.WebSocket"] = None
        self._lock = threading.Lock()

    def available(self) -> bool:
        return websocket is not None

    def connect(self, timeout: float = 3.0) -> bool:
        if websocket is None:
            return False
        try:
            self.ws = websocket.create_connection(self.url, timeout=timeout)
            # Minimal hello (optional in VTS v1.0+), kept lean for stub
            return True
        except Exception:
            self.ws = None
            return False

    def disconnect(self) -> None:
        with self._lock:
            try:
                if self.ws is not None:
                    self.ws.close()
            except Exception:
                pass
            self.ws = None

    def set_parameter(self, name: str, value: float) -> bool:
        """Set a Live2D parameter value (e.g., MouthOpen, EyeSmile).

        This uses the VTS request `InjectParameterData`.
        """
        if self.ws is None:
            return False
        payload = {
            "apiName": "VTubestudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": f"param-{int(time.time()*1000)}",
            "messageType": "InjectParameterData",
            "data": {
                "param": {
                    "name": name,
                    "value": float(value),
                    "weight": 1.0,
                    "isAdditive": False,
                },
                "faceFound": True,
                "mode": "set",
            },
        }
        try:
            with self._lock:
                self.ws.send(json.dumps(payload))
            return True
        except Exception:
            return False

    def test_emote(self) -> bool:
        """Trigger a simple visual change for validation.

        Attempts to set `MouthOpen` and `EyeSmile` briefly.
        """
        ok1 = self.set_parameter("MouthOpen", 0.8)
        ok2 = self.set_parameter("EyeSmile", 0.6)
        time.sleep(0.5)
        self.set_parameter("MouthOpen", 0.0)
        self.set_parameter("EyeSmile", 0.0)
        return ok1 or ok2
