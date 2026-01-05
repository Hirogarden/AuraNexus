Place your identifying image here:
- aura_nexus.png (source image; used by the window)
- aura_nexus.ico (icon file; embedded into the exe if present)

Recommended: 512x512 or 1024x1024 PNG with transparent background.

Generate .ico from .png:
1) .\.venv\Scripts\Activate.ps1
2) python -m pip install pillow
3) python .\tools\make_icon.py

Then rebuild the exe with icon embedding:
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
