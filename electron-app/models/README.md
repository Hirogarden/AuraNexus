# AuraNexus Models Directory

## 🚀 First-Time Setup

AuraNexus will **automatically download a small starter model** (~350MB) on first launch!

The starter model (Qwen2.5-0.5B-Instruct) is:
- ✅ Fast and responsive
- ✅ Works on any computer (CPU or GPU)
- ✅ Great for trying out features
- ✅ HIPAA-compliant (runs locally, no cloud)

## 📥 Starter Model

- **Name**: Qwen2.5-0.5B-Instruct (Q4_K_M)
- **Size**: ~350MB
- **Speed**: Very fast (~20-50 tokens/sec on CPU)
- **Quality**: Good for chat, stories, basic assistance
- **Auto-downloads**: Yes, on first run

## 🎯 Recommended Models

Want better quality? Drop any of these into this folder:

### For Faster Computers (8GB+ RAM)
- **Llama-3.2-3B-Instruct** (Q4_K_M, ~2GB)
  - Excellent quality/speed balance
  - Good for storytelling and complex tasks

### For Powerful Computers (16GB+ RAM, GPU recommended)
- **Llama-3.1-8B-Instruct** (Q4_K_M, ~4.5GB)
  - High-quality responses
  - Great for medical assistant use
  
- **Qwen2.5-7B-Instruct** (Q4_K_M, ~4.4GB)
  - Exceptional reasoning
  - Multilingual support

### For Maximum Quality (32GB+ RAM, GPU required)
- **Llama-3.1-70B-Instruct** (Q4_K_M, ~40GB)
  - Professional-grade responses
  - Best for critical medical conversations

## 📦 Where to Get Models

1. **Hugging Face** (recommended): https://huggingface.co/models?library=gguf
2. **TheBloke's GGUF models**: Look for Q4_K_M or Q5_K_M quantizations

## 🔧 Manual Installation

1. Download a `.gguf` model file
2. Place it in this `models/` folder
3. Restart AuraNexus
4. It will auto-detect and load!

## ⚙️ Advanced: Model Selection

If you have multiple models, AuraNexus loads the first `.gguf` file it finds.
To choose a specific model:
- Remove or rename other `.gguf` files
- Or use the Settings menu (coming soon!)

## 🔒 HIPAA Compliance Note

All models run **100% locally** on your computer. No data ever leaves your device.
This ensures full HIPAA compliance for medical/mental health conversations.

## 💡 Pro Tips

- **Q4_K_M** quantization = best quality/size balance
- **Q5_K_M** = slightly better quality, larger size
- **Q2_K** = smallest but lower quality (not recommended)
- GPU makes models 5-10x faster!
- Larger models = better quality but slower

## 🆘 Troubleshooting

**Model won't load?**
- Check it's a `.gguf` file (not `.bin` or `.safetensors`)
- Ensure enough RAM (model size + 2GB minimum)
- Check logs in console for error messages

**Too slow?**
- Try a smaller model (1B-3B)
- Enable GPU acceleration if you have one
- Reduce context window in settings

**Want to upgrade?**
- Just drop a new model in this folder!
- Remove the old one to save space
- Restart the app
