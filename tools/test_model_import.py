"""Test model import with paths containing spaces."""
import requests
import json
import sys
from pathlib import Path

def test_import(file_path: str, model_name: str = "test-import:latest"):
    """Test importing a model with the given file path."""
    
    print(f"\n{'='*60}")
    print(f"Testing import of: {file_path}")
    print(f"Model name: {model_name}")
    
    # Check if file exists
    if not Path(file_path).exists():
        print(f"WARNING: File does not exist!")
        print(f"This test will still run to show what request would be sent.")
    else:
        file_size = Path(file_path).stat().st_size / (1024 * 1024)
        print(f"File size: {file_size:.2f} MB")
    
    print(f"{'='*60}\n")
    
    # Convert to forward slashes
    modelfile_path = file_path.replace('\\', '/')
    
    # Test different quoting strategies
    # Note: Ollama expects lowercase 'from' not 'FROM'
    strategies = [
        ("Lowercase from + single quotes", f"from '{modelfile_path}'"),
        ("Lowercase from + double quotes", f'from "{modelfile_path}"'),
        ("Lowercase from + no quotes", f"from {modelfile_path}"),
        ("Uppercase FROM + single quotes", f"FROM '{modelfile_path}'"),
        ("Uppercase FROM + double quotes", f'FROM "{modelfile_path}"'),
    ]
    
    base_url = "http://localhost:11434"
    
    # First check if Ollama is running
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=2)
        print("✓ Ollama is running\n")
    except:
        print("✗ Ollama is not running. Please start Ollama first.\n")
        return False
    
    for name, modelfile in strategies:
        print(f"\n--- Strategy: {name} ---")
        print(f"Modelfile: {repr(modelfile)}")
        
        payload = {
            "model": model_name,
            "modelfile": modelfile,
            "stream": False
        }
        
        print(f"JSON payload:")
        print(json.dumps(payload, indent=2))
        
        try:
            resp = requests.post(
                f"{base_url}/api/create",
                json=payload,
                timeout=30
            )
            
            print(f"\nStatus code: {resp.status_code}")
            
            if resp.status_code == 200:
                print(f"✓ SUCCESS! This format works!")
                try:
                    response_data = resp.json()
                    print(f"Response: {json.dumps(response_data, indent=2)}")
                except:
                    print(f"Response: {resp.text}")
                
                # Clean up - delete the test model
                try:
                    del_resp = requests.delete(
                        f"{base_url}/api/delete",
                        json={"name": model_name}
                    )
                    print(f"Cleaned up test model.")
                except:
                    pass
                
                return True
            else:
                print(f"✗ FAILED")
                print(f"Response: {resp.text}")
                
        except Exception as e:
            print(f"✗ ERROR: {e}")
        
        print()
    
    return False

if __name__ == "__main__":
    print("="*60)
    print("Ollama Model Import Path Testing Utility")
    print("="*60)
    
    # Test with a path that has spaces
    if len(sys.argv) > 1:
        test_path = sys.argv[1]
        if len(sys.argv) > 2:
            model_name = sys.argv[2]
        else:
            model_name = "test-import:latest"
    else:
        print("\nUsage: python test_model_import.py <path_to_gguf> [model_name]")
        print("\nExample:")
        print('  python test_model_import.py "C:/Users/Test User/Models/my model.gguf"')
        print('  python test_model_import.py "C:/path/to/model.gguf" my-model:latest')
        print("\nNo path provided. Using example path for demonstration...")
        test_path = "C:/Users/Test User/Models/example model.gguf"
        model_name = "test-import:latest"
    
    success = test_import(test_path, model_name)
    
    if success:
        print("\n" + "="*60)
        print("✓ SUCCESS! Found a working format.")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("✗ All formats failed or Ollama is not running.")
        print("="*60)

