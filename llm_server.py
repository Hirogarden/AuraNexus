"""
Simple HTTP server for LLM that Tauri can call
Run this separately and it handles all the model loading
"""
from flask import Flask, request, jsonify
import sys
import os

# Add backend to path
sys.path.insert(0, r"C:\Users\hirog\All-In-One\AuraNexus\electron-app.OLD\backend")
import llm_manager

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt', '')
    system_prompt = data.get('system_prompt')
    conversation_history = data.get('conversation_history', [])
    
    # Extract sampling params
    kwargs = {
        'temperature': data.get('temperature', 0.7),
        'top_p': data.get('top_p', 0.95),
        'top_k': data.get('top_k', 40),
        'max_tokens': data.get('max_tokens', 512),
    }
    
    # Generate response
    try:
        response_text = llm_manager.generate_with_context(
            prompt=prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            **kwargs
        )
        return jsonify({'response': response_text, 'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/health', methods=['GET'])
def health():
    model_loaded = llm_manager.get_llm_instance() is not None
    return jsonify({'status': 'ok', 'model_loaded': model_loaded})

if __name__ == '__main__':
    print("=" * 60)
    print("AuraNexus LLM Server Starting...")
    print("=" * 60)
    
    # Pre-load the small model for instant responses
    model_path = "models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
    if os.path.exists(model_path):
        print(f"Loading model: {model_path}")
        llm_manager.load_model(model_path, n_ctx=2048, n_gpu_layers=20)
        print("Model loaded and ready!")
    else:
        print("Model will auto-load on first request")
    
    print(f"Server running on http://localhost:5555")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5555, debug=False, threaded=True)
