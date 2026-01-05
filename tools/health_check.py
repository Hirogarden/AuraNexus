import sys

def main() -> int:
    try:
        import PySide6
        import requests
        import pyttsx3
        import websocket
    except Exception as e:
        print(f"[health] Import error: {e}")
        return 1
    print("[health] All core imports succeeded.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
