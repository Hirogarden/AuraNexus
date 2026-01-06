# Structured Outputs & Tool Calling Features

This document describes the new structured outputs and tool calling features added to AuraNexus.

## Overview

Two major features have been implemented based on Ollama API documentation:

1. **Structured Outputs**: Force models to return valid JSON matching a specific schema
2. **Tool Calling**: Allow models to execute Python functions to perform actions

## Feature 1: Structured Outputs

### What is it?
Structured outputs ensure the model returns valid JSON that conforms to a predefined schema. This is useful for:
- Extracting structured data from text
- Building reliable APIs
- Ensuring consistent output formats
- Validating responses automatically

### Usage

#### Simple JSON Mode
```python
from ollama_client import OllamaClient, Message

client = OllamaClient()
messages = [Message(role="user", content="List 3 colors in JSON")]

# Enable simple JSON mode
response = client.chat(messages, format="json")
print(response['content'])  # Guaranteed to be valid JSON
```

#### With JSON Schema
```python
# Define exact structure you want
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "email": {"type": "string"}
    },
    "required": ["name", "age"]
}

messages = [Message(role="user", content="Create profile for Alice, 28")]
response = client.chat(messages, format=schema)

# Response will match schema exactly
import json
data = json.loads(response['content'])
print(data['name'])  # "Alice"
print(data['age'])   # 28
```

### In the GUI

```python
# Enable JSON mode in your chat window
chat_window.set_json_format()  # Simple JSON mode

# Or with schema
schema = {...}
chat_window.set_json_format(schema)

# Disable
chat_window.clear_format()
```

## Feature 2: Tool Calling (Function Calling)

### What is it?
Tool calling allows models to execute real Python functions to:
- Perform calculations
- Access real-time data (time, weather, etc.)
- Interact with your system (file operations, API calls)
- Execute custom business logic

### Built-in Tools

AuraNexus comes with these tools pre-configured:

1. **get_current_time**: Returns current date/time
2. **calculate**: Evaluates math expressions (sqrt, sin, cos, etc.)
3. **list_files**: Lists files in a directory

### Usage

#### Programmatic
```python
from ollama_client import OllamaClient, Message

client = OllamaClient()

# Define tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"}
                },
                "required": ["city"]
            }
        }
    }
]

messages = [Message(role="user", content="What's the weather in Tokyo?")]

# Model will call the tool
response = client.chat(messages, tools=tools)

if 'tool_calls' in response:
    for call in response['tool_calls']:
        func_name = call['function']['name']
        args = call['function']['arguments']
        print(f"Model wants to call: {func_name}({args})")
        
        # Execute tool (you implement this)
        result = execute_tool(func_name, args)
        
        # Send result back to model
        messages.append(Message(role="tool", content=result, tool_name=func_name))
        final_response = client.chat(messages, tools=tools)
        print(final_response['content'])
```

#### In the GUI

The GUI automatically handles tool execution:

```python
# Enable tools
chat_window.enable_tools()

# User types: "What time is it?"
# -> Model calls get_current_time()
# -> Tool executes automatically
# -> Result sent back to model
# -> Model responds with formatted answer
```

### Adding Custom Tools

```python
# Define your tool
custom_tools = [
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "Search customer database",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["query"]
            }
        }
    }
]

# Add to available tools
chat_window.available_tools.extend(custom_tools)

# Implement execution logic
original_execute = chat_window.execute_tool

def custom_execute_tool(tool_name, arguments):
    if tool_name == "search_database":
        query = arguments['query']
        # Your database search logic here
        results = search_db(query)
        return f"Found {len(results)} results"
    else:
        return original_execute(tool_name, arguments)

chat_window.execute_tool = custom_execute_tool
```

## Testing

Run the test suite:
```bash
python tools/test_features.py
```

Run the interactive demo:
```bash
python tool_demo.py
```

## Examples

### Example 1: Extract Contact Info
```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"}
    }
}

messages = [Message(role="user", content="""
Extract contact info from this text:
"Hi, I'm John Smith. You can reach me at john@example.com or call 555-1234"
""")]

response = client.chat(messages, format=schema)
contact = json.loads(response['content'])
```

### Example 2: Multi-Tool Query
```python
messages = [Message(role="user", content="What time is it and what's 25 * 17?")]

# Model will call both tools
response = client.chat(messages, tools=[...])

# Process tool calls
for call in response['tool_calls']:
    result = execute_tool(call['function']['name'], call['function']['arguments'])
    messages.append(Message(role="tool", content=result))

# Get final answer
final = client.chat(messages, tools=[...])
print(final['content'])  # "It's currently 2:30 PM and 25 * 17 equals 425"
```

### Example 3: Code Generation with Validation
```python
schema = {
    "type": "object",
    "properties": {
        "language": {"type": "string"},
        "code": {"type": "string"},
        "explanation": {"type": "string"}
    },
    "required": ["language", "code"]
}

messages = [Message(role="user", content="Write a Python function to reverse a string")]
response = client.chat(messages, format=schema)

result = json.loads(response['content'])
print(f"Language: {result['language']}")
print(f"Code:\n{result['code']}")
```

## API Changes

### Breaking Changes
None! The API is backward compatible. Old code will continue to work.

### New Parameters

**OllamaClient.chat()**
- `format` (dict|str): JSON schema or "json" for simple mode
- `tools` (list): Tool definitions for function calling

**OllamaClient.chat_stream()**
- Same new parameters as chat()
- Yields dict with `content` and optionally `tool_calls`

**Message dataclass**
- `tool_calls` (list): Tool calls from model
- `tool_name` (str): For tool result messages

### Return Values

**Old behavior** (still works):
```python
response = client.chat(messages)
print(response)  # Now returns dict instead of str
```

**New behavior**:
```python
response = client.chat(messages)
print(response['content'])      # The message content
print(response.get('tool_calls'))  # Tool calls if present
```

## Model Compatibility

### Structured Outputs
Works with most modern models:
- ✅ Llama 3.1, 3.2, 3.3 (8B+)
- ✅ Mistral
- ✅ Gemma
- ❓ Older models may not follow schema strictly

### Tool Calling
Requires models trained for function calling:
- ✅ Llama 3.2+
- ✅ Mistral
- ✅ Command-R
- ❌ Base Llama 2 (not trained for tools)

Check model capabilities: https://ollama.com/search?c=tool

## Troubleshooting

### Schema Not Followed
- Use more explicit descriptions in schema
- Add examples in the prompt
- Try a larger model (8B+)

### Tools Not Called
- Make prompt more explicit: "Use your tools to..."
- Check model supports tool calling
- Verify tool descriptions are clear

### Empty Tool Results
- Check tool execution logic
- Ensure tool returns string
- Add error handling in execute_tool()

## Performance Notes

- Structured outputs add ~5-10% latency
- Tool calling requires 2 round trips (model → tool → model)
- Streaming works but tool calls arrive at end
- Consider caching tool results

## Security Considerations

### Safe Tool Execution
The built-in `calculate` tool uses restricted `eval()`:
- No access to `__builtins__`
- Limited to math functions
- Cannot execute arbitrary code

### File Access
The `list_files` tool:
- Does NOT follow symlinks by default
- Truncates results at 20 items
- Should be restricted to specific directories in production

### Custom Tools
When adding custom tools:
- Validate all inputs
- Sanitize file paths
- Rate limit expensive operations
- Never pass user input directly to shell
- Use allowlists, not blocklists

## Future Enhancements

Potential additions:
- [ ] Vision tools (image analysis)
- [ ] Web search integration
- [ ] Database query tools
- [ ] Email/notification tools
- [ ] File read/write tools (with safety)
- [ ] Tool call caching
- [ ] Parallel tool execution
- [ ] Tool result streaming

## References

- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [JSON Schema Specification](https://json-schema.org/)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling) (similar concepts)

## Support

For issues or questions:
1. Check [tools/test_features.py](../tools/test_features.py) for working examples
2. Run `python tool_demo.py` for interactive testing
3. See [src/ollama_client.py](../src/ollama_client.py) for implementation details
