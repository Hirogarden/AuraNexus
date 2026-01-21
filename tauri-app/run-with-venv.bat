@echo off
REM Activate venv and run Tauri app with correct Python
call "C:\Users\hirog\All-In-One\AuraNexus\.venv\Scripts\activate.bat"
cd /d "C:\Users\hirog\All-In-One\AuraNexus\tauri-app\src-tauri"
cargo run
