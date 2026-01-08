"""Test script for structured outputs and tool calling features."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ollama_client import OllamaClient, Message
import json


def test_structured_output():
    """Test structured JSON output with schema."""
    print("\n" + "="*60)
    print("TEST 1: Structured Output (JSON Schema)")
    print("="*60)
    
    client = OllamaClient(model="llama3.2:latest")
    
    # Define a schema for user info
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "hobbies": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["name", "age"]
    }
    
    messages = [
        Message(role="user", content="Create a profile for a person named Alice who is 28 years old and likes reading and hiking")
    ]
    
    print("\nRequest: Create structured profile")
    print(f"Schema: {json.dumps(schema, indent=2)}")
    
    response = client.chat(messages, format=schema)
    
    print(f"\nResponse type: {type(response)}")
    print(f"Content: {response.get('content', '')}")
    
    # Try to parse the JSON
    try:
        data = json.loads(response.get('content', '{}'))
        print(f"\nParsed JSON:")
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError as e:
        print(f"\nJSON parsing failed: {e}")


def test_json_mode():
    """Test simple JSON mode."""
    print("\n" + "="*60)
    print("TEST 2: Simple JSON Mode")
    print("="*60)
    
    client = OllamaClient(model="llama3.2:latest")
    
    messages = [
        Message(role="user", content="List 3 colors and their hex codes in JSON format")
    ]
    
    print("\nRequest: List colors in JSON")
    
    response = client.chat(messages, format="json")
    
    print(f"\nResponse: {response.get('content', '')}")
    
    try:
        data = json.loads(response.get('content', '{}'))
        print(f"\nParsed JSON:")
        print(json.dumps(data, indent=2))
    except json.JSONDecodeError as e:
        print(f"\nJSON parsing failed: {e}")


def test_tool_calling():
    """Test tool/function calling."""
    print("\n" + "="*60)
    print("TEST 3: Tool Calling")
    print("="*60)
    
    client = OllamaClient(model="llama3.2:latest")
    
    # Define tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather in a given city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The city to get the weather for"
                        }
                    },
                    "required": ["city"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Perform a mathematical calculation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "The mathematical expression to evaluate"
                        }
                    },
                    "required": ["expression"]
                }
            }
        }
    ]
    
    messages = [
        Message(role="user", content="What's the weather in Tokyo and what's 25 * 4?")
    ]
    
    print("\nRequest: Multi-tool query")
    print(f"Available tools: {len(tools)}")
    
    response = client.chat(messages, tools=tools)
    
    print(f"\nResponse: {response}")
    
    if response.get('tool_calls'):
        print(f"\nTool calls detected: {len(response['tool_calls'])}")
        for i, call in enumerate(response['tool_calls']):
            func = call.get('function', {})
            print(f"\n  Tool {i+1}: {func.get('name')}")
            print(f"  Arguments: {json.dumps(func.get('arguments', {}), indent=4)}")
    else:
        print("\nNo tool calls (model may have responded directly)")
        print(f"Content: {response.get('content', '')}")


def test_backward_compatibility():
    """Test that old code still works."""
    print("\n" + "="*60)
    print("TEST 4: Backward Compatibility")
    print("="*60)
    
    client = OllamaClient(model="llama3.2:latest")
    
    messages = [
        Message(role="user", content="Say hello in 5 words")
    ]
    
    print("\nRequest: Simple chat (no special features)")
    
    response = client.chat(messages)
    
    print(f"\nResponse type: {type(response)}")
    print(f"Content: {response.get('content', '')[:100]}...")


if __name__ == "__main__":
    print("\n🧪 Testing Ollama New Features")
    print("Make sure Ollama is running with a model available!")
    
    try:
        # Test 1: Structured outputs
        test_structured_output()
        
        # Test 2: Simple JSON mode
        test_json_mode()
        
        # Test 3: Tool calling
        test_tool_calling()
        
        # Test 4: Backward compatibility
        test_backward_compatibility()
        
        print("\n" + "="*60)
        print("✅ All tests completed!")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\n❌ Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
