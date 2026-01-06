"""Interactive test application for new Ollama features."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ollama_client import OllamaClient


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60 + "\n")


def test_generate():
    """Test the generate endpoint interactively."""
    print_header("Text Generation (Generate API)")
    
    client = OllamaClient()
    print("This uses /api/generate for simple text completion.")
    print("Good for one-off generations without conversation history.\n")
    
    prompt = input("Enter your prompt (or press Enter for default): ").strip()
    if not prompt:
        prompt = "Write a short poem about artificial intelligence"
    
    print(f"\nGenerating response to: '{prompt}'\n")
    print("Response:")
    print("-" * 60)
    
    result = client.generate(prompt)
    if "error" in result:
        print(f"❌ Error: {result['error']}")
    else:
        print(result['response'])
        print("-" * 60)
        print(f"\nMetadata:")
        print(f"  Tokens generated: {result.get('eval_count', 0)}")
        print(f"  Time: {result.get('total_duration', 0) / 1e9:.2f}s")


def test_streaming():
    """Test streaming generation."""
    print_header("Streaming Generation")
    
    client = OllamaClient()
    print("This streams tokens as they're generated (lower latency).\n")
    
    prompt = input("Enter your prompt (or press Enter for default): ").strip()
    if not prompt:
        prompt = "Count from 1 to 10"
    
    print(f"\nStreaming response to: '{prompt}'\n")
    print("Response: ", end="", flush=True)
    
    token_count = 0
    for chunk in client.generate_stream(prompt):
        if "error" in chunk:
            print(f"\n❌ Error: {chunk['error']}")
            break
        
        response = chunk.get("response", "")
        if response:
            print(response, end="", flush=True)
            token_count += 1
        
        if chunk.get("done"):
            print(f"\n\n✓ Streamed {token_count} chunks")
            break


def test_model_copy():
    """Test model copying."""
    print_header("Model Copying")
    
    client = OllamaClient()
    print("Copy a model to create a backup or variant.\n")
    
    models = client.list_models()
    print("Available models:")
    for i, model in enumerate(models, 1):
        print(f"  {i}. {model}")
    
    choice = input("\nEnter model number to copy (or press Enter to skip): ").strip()
    if not choice:
        print("Skipped")
        return
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(models):
            source = models[idx]
            default_dest = f"{source.split(':')[0]}-copy:latest"
            dest = input(f"Destination name [{default_dest}]: ").strip() or default_dest
            
            print(f"\nCopying {source} → {dest}...")
            if client.copy_model(source, dest):
                print("✓ Model copied successfully!")
                
                # Verify
                updated = client.list_models()
                if dest in updated:
                    print(f"✓ Verified: {dest} is now available")
                    
                    # Offer to delete
                    delete = input("\nDelete the copy? (y/N): ").strip().lower()
                    if delete == 'y':
                        client.delete_model(dest)
                        print(f"✓ Deleted {dest}")
            else:
                print("❌ Failed to copy model")
        else:
            print("Invalid choice")
    except ValueError:
        print("Invalid input")


def test_version():
    """Test version check."""
    print_header("Ollama Version Check")
    
    client = OllamaClient()
    version = client.get_version()
    
    if version:
        print(f"✓ Ollama version: {version}")
        print(f"\nYour Ollama server is running and accessible!")
    else:
        print("❌ Could not retrieve version")
        print("Is Ollama running? Try: ollama serve")


def test_memory():
    """Test memory management."""
    print_header("Memory Management")
    
    client = OllamaClient()
    
    print("1. Current loaded models:")
    result = client.list_running_models()
    
    if "error" in result:
        print(f"   ❌ Error: {result['error']}")
        return
    
    models = result.get("models", [])
    if not models:
        print("   No models currently loaded in memory")
    else:
        total_ram = 0
        total_vram = 0
        for m in models:
            name = m.get("name", "Unknown")
            size = m.get("size", 0)
            vram = m.get("size_vram", 0)
            total_ram += size
            total_vram += vram
            
            print(f"\n   • {name}")
            print(f"     RAM: {size / (1024**3):.2f} GB")
            print(f"     VRAM: {vram / (1024**3):.2f} GB")
        
        print(f"\n   Total RAM: {total_ram / (1024**3):.2f} GB")
        print(f"   Total VRAM: {total_vram / (1024**3):.2f} GB")
    
    # Offer to unload
    if models:
        unload = input("\nUnload a model? (y/N): ").strip().lower()
        if unload == 'y':
            print("\nAvailable to unload:")
            for i, m in enumerate(models, 1):
                print(f"  {i}. {m.get('name')}")
            
            choice = input("\nEnter model number: ").strip()
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    model_name = models[idx]["name"]
                    if client.unload_model(model_name):
                        print(f"✓ Unloaded {model_name}")
                    else:
                        print(f"❌ Failed to unload {model_name}")
            except ValueError:
                print("Invalid input")


def test_embeddings():
    """Test embeddings."""
    print_header("Embeddings (Vector Generation)")
    
    client = OllamaClient()
    print("Generate vector embeddings for semantic search and RAG.\n")
    
    text = input("Enter text to embed (or press Enter for default): ").strip()
    if not text:
        text = "Hello, world!"
    
    print(f"\nGenerating embedding for: '{text}'")
    result = client.embed(text)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
    else:
        embeddings = result.get("embeddings", [])
        if embeddings:
            embedding = embeddings[0]
            print(f"\n✓ Generated embedding:")
            print(f"   Dimensions: {len(embedding)}")
            print(f"   First 10 values: {embedding[:10]}")
            print(f"   Model: {result.get('model', 'unknown')}")


def show_menu():
    """Show the main menu."""
    print("\n" + "=" * 60)
    print("INTERACTIVE OLLAMA FEATURE TEST")
    print("=" * 60)
    print("\n1. Text Generation (Generate API)")
    print("2. Streaming Generation")
    print("3. Model Copying")
    print("4. Version Check")
    print("5. Memory Management")
    print("6. Embeddings")
    print("7. Run All Tests")
    print("0. Exit")
    print()


def main():
    """Main interactive loop."""
    while True:
        show_menu()
        choice = input("Choose an option (0-7): ").strip()
        
        if choice == "0":
            print("\nGoodbye!")
            break
        elif choice == "1":
            test_generate()
        elif choice == "2":
            test_streaming()
        elif choice == "3":
            test_model_copy()
        elif choice == "4":
            test_version()
        elif choice == "5":
            test_memory()
        elif choice == "6":
            test_embeddings()
        elif choice == "7":
            test_version()
            test_memory()
            test_embeddings()
            test_generate()
            print("\n✓ All quick tests complete!")
        else:
            print("\n❌ Invalid choice. Please enter 0-7.")
        
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
