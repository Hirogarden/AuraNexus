# Timestamp Feature Implementation

**Status:** ✅ Complete  
**Date:** January 5, 2026  
**Feature:** Time-aware conversation context

---

## Overview

Implemented comprehensive timestamp support across all conversation features, enabling time-aware responses and context about user activity patterns.

---

## Key Features

### 1. Automatic Timestamps

Every message now includes a timestamp:
- **User messages**: Timestamped when sent
- **Assistant messages**: Timestamped when generated
- **Preserved in saved conversations**: Full conversation history maintained

### 2. Time Gap Detection

System automatically detects and responds to time gaps:

| Gap Duration | Behavior | Example Context |
|--------------|----------|-----------------|
| < 5 minutes | Continue naturally | `[Context: User is actively chatting]` |
| 5-60 minutes | Brief acknowledgment | `[Context: User stepped away for 30 minutes and has returned]` |
| 1-4 hours | Ask about activities | `[Context: User has been away for 2 hours. They may have been doing other tasks]` |
| 4-24 hours | Ask about their day | `[Context: User has been gone for 8 hours. Consider asking how their day went]` |
| > 1 day | Show interest | `[Context: User has been away for 2 days. Consider asking what they've been up to]` |

### 3. Context Injection

Time context is automatically added to the system prompt when gaps > 30 minutes are detected, enabling the bot to:
- Acknowledge time away naturally
- Ask appropriate questions ("How was your day?")
- Be contextually aware in storytelling
- Remember last interaction timing

### 4. Visual Timestamps

Messages display with formatted timestamps:
```
🧑 You (08:42 PM):
Hello!

🤖 Aura (08:42 PM):
Hi! How can I help you today?
```

---

## Implementation Details

### New Module: `src/time_utils.py`

**Functions:**

1. **`calculate_time_elapsed(start, end=None)`**
   - Calculates time between two timestamps
   - Defaults to current time if end not provided

2. **`format_time_elapsed(elapsed)`**
   - Human-readable formatting ("2 hours and 30 minutes")
   - Smart unit selection (seconds → minutes → hours → days)

3. **`generate_time_context_prompt(last_message_time)`**
   - Creates context string for system prompt
   - Behavior suggestions based on elapsed time

4. **`format_timestamp_for_display(timestamp, include_date=False)`**
   - Formats timestamps for chat display
   - Optional date inclusion

5. **`should_acknowledge_time_gap(elapsed)`**
   - Returns True if gap > 30 minutes
   - Used to determine when to inject context

6. **`get_time_of_day_greeting()`**
   - Returns appropriate greeting based on time
   - "Good morning", "Good afternoon", "Good evening"

### Updated: `src/ollama_client.py`

**Message Dataclass Enhancement:**

```python
@dataclass
class Message:
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)  # NEW
    
    def to_dict(self) -> Dict:
        # Serialization with timestamp
        
    @classmethod
    def from_dict(cls, d: Dict) -> 'Message':
        # Deserialization with timestamp restoration
```

### Updated: `src/ollama_chat.py`

**Key Changes:**

1. **Import time utilities**
2. **Enhanced `append_message()`** - Shows timestamps in display
3. **Enhanced `send_message()`** - Generates time context
4. **Enhanced `on_response()`** - Adds timestamps to assistant messages
5. **Enhanced `save_conversation()`** - Preserves timestamps in JSON
6. **Enhanced `load_conversation()`** - Restores timestamps from JSON

---

## Usage Examples

### Time Context in Action

**Scenario 1: Quick Reply (2 minutes)**
```
User (2:30 PM): "What's 2+2?"
Bot (2:30 PM): "2+2 equals 4."
User (2:32 PM): "Thanks!"
Bot (2:32 PM): "You're welcome!"
```
*No time context injected - active conversation*

**Scenario 2: Stepped Away (45 minutes)**
```
User (2:30 PM): "What's 2+2?"
Bot (2:30 PM): "2+2 equals 4."
User (3:15 PM): "What about 5+5?"
Bot (3:15 PM): "Welcome back! 5+5 equals 10."
```
*Context: `[Context: User stepped away for 45 minutes and has returned]`*

**Scenario 3: Long Break (8 hours)**
```
User (9:00 AM): "Good morning!"
Bot (9:00 AM): "Good morning! How can I help?"
User (5:00 PM): "I'm back!"
Bot (5:00 PM): "Welcome back! How was your day? It's been about 8 hours since we last chatted."
```
*Context: `[Context: User has been gone for 8 hours. Consider asking how their day went]`*

### Conversation Persistence

**Save with Timestamps:**
```json
{
  "project": "AuraNexus Chat",
  "timestamp": "2026-01-05T20:42:00",
  "messages": [
    {
      "role": "user",
      "content": "Hello!",
      "timestamp": "2026-01-05T14:30:00"
    },
    {
      "role": "assistant",
      "content": "Hi there!",
      "timestamp": "2026-01-05T14:30:05"
    }
  ]
}
```

**Load Preserved Conversation:**
- Timestamps restored correctly
- Time gap detection works on loaded conversations
- Historical context maintained

---

## Storytelling Integration

The timestamp feature is particularly powerful for storytelling:

**Example: Interactive Story**
```
User (2:00 PM): "Let's write a story about a knight."
Bot (2:00 PM): "Once upon a time, there was a brave knight..."

[User takes 3-hour break]

User (5:00 PM): "Continue the story."
Bot (5:00 PM): "Welcome back! After the knight defeated the dragon (we left off 3 hours ago), the knight decided to..."
```

The bot can:
- Reference real-world time in story progression
- Create time-based story elements
- Acknowledge breaks in the narrative
- Use elapsed time creatively in plots

---

## Companion Mode Benefits

For companion/assistant interactions:

1. **Natural Conversations**
   - "Oh, you're back after lunch?"
   - "Good evening! It's been a few hours."
   - "Did you have a good day?"

2. **Context Awareness**
   - Remembers when you last talked
   - Adjusts greeting based on time of day
   - Shows care/interest appropriately

3. **Session Management**
   - Tracks conversation sessions
   - Identifies new vs continuing conversations
   - Better context retention

---

## Technical Implementation

### Time Gap Detection Flow

```python
# In send_message():
if len(self.messages) > 1:
    # Find last user message
    for msg in reversed(self.messages[:-1]):
        if msg.role == "user":
            elapsed = calculate_time_elapsed(msg.timestamp, user_message.timestamp)
            if should_acknowledge_time_gap(elapsed):
                time_context = generate_time_context_prompt(msg.timestamp)
            break

# Time context added to system prompt
if time_context:
    augmented_prompt = f"{augmented_prompt}\n\n{time_context}"
```

### Timestamp Display

```python
def append_message(self, role: str, content: str, timestamp: datetime = None):
    time_str = ""
    if timestamp:
        time_str = f" ({format_timestamp_for_display(timestamp)})"
    
    if role == "user":
        cursor.insertText(f"\n🧑 You{time_str}:\n{content}\n")
```

---

## Testing Results

```bash
$ python src/time_utils.py

Time Formatting:
  30 seconds -> 30 seconds
  5:00 -> 5 minutes
  45:00 -> 45 minutes
  2:30:00 -> 2 hours and 30 minutes
  1 day -> 1 day
  2 days, 5:00:00 -> 2 days and 5 hours

Time Context Prompts:
  2 minutes ago: [Context: User is actively chatting]
  30 minutes ago: [Context: User stepped away for 30 minutes and has returned]
  8 hours ago: [Context: User has been gone for 8 hours. Consider asking how their day went]
```

---

## Benefits

### For Users

1. **Natural Interactions**
   - Bot acknowledges time away
   - Feels more human and aware
   - Appropriate contextual responses

2. **Story Continuity**
   - Better narrative flow
   - Time-aware story progression
   - Real-world time integration

3. **Conversation Memory**
   - Full timestamp history in saved conversations
   - Can review when conversations happened
   - Better context on reloading

### For Development

1. **Extensible Framework**
   - Easy to add more time-based behaviors
   - Modular time utilities
   - Reusable across all features

2. **Data Rich**
   - Analytics on conversation patterns
   - Session duration tracking
   - User activity insights

---

## Future Enhancements

### Potential Additions

1. **Time-Based Reminders**
   ```python
   "You mentioned wanting to finish that task. It's been 4 hours - how's it going?"
   ```

2. **Daily Summaries**
   ```python
   "We've chatted for 2 hours today across 5 sessions."
   ```

3. **Smart Session Breaks**
   ```python
   "You've been working for 3 hours - might be a good time for a break?"
   ```

4. **Historical Context**
   ```python
   "Last time we talked (2 days ago), you were working on that project. How did it go?"
   ```

5. **Scheduled Responses**
   ```python
   "Based on our chat history, you usually take a break around this time."
   ```

---

## Related Files

- **`src/ollama_client.py`** - Message dataclass with timestamps
- **`src/time_utils.py`** - Time utility functions
- **`src/ollama_chat.py`** - Chat UI with timestamp display and context
- **Companion app** - Will benefit from same timestamp system
- **Storytelling features** - Time-aware narrative generation

---

## Integration Checklist

✅ Message dataclass updated with timestamps  
✅ Automatic timestamp generation  
✅ Time gap detection (>30 minutes)  
✅ Context prompt generation  
✅ Visual timestamp display in chat  
✅ Conversation save/load preserves timestamps  
✅ Time utilities module created  
✅ Integration tested and working  
✅ Companion mode ready for enhancement  
✅ Storytelling features time-aware  

---

*Feature Complete - Time-Aware Conversations Operational*
