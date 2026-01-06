"""
Time utilities for conversation context awareness.

Provides functions to calculate time elapsed between messages and
generate context-aware prompts.

Author: AuraNexus
Created: 2026
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple


def calculate_time_elapsed(start: datetime, end: Optional[datetime] = None) -> timedelta:
    """
    Calculate time elapsed between two timestamps.
    
    Args:
        start: Start timestamp
        end: End timestamp (default: now)
        
    Returns:
        timedelta representing elapsed time
    """
    if end is None:
        end = datetime.now()
    return end - start


def format_time_elapsed(elapsed: timedelta) -> str:
    """
    Format elapsed time in human-readable form.
    
    Args:
        elapsed: timedelta object
        
    Returns:
        Human-readable string (e.g., "5 minutes", "2 hours", "3 days")
    """
    total_seconds = int(elapsed.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds} second{'s' if total_seconds != 1 else ''}"
    
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    
    hours = minutes // 60
    if hours < 24:
        remaining_minutes = minutes % 60
        if remaining_minutes > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} and {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
        return f"{hours} hour{'s' if hours != 1 else ''}"
    
    days = hours // 24
    remaining_hours = hours % 24
    if remaining_hours > 0:
        return f"{days} day{'s' if days != 1 else ''} and {remaining_hours} hour{'s' if remaining_hours != 1 else ''}"
    return f"{days} day{'s' if days != 1 else ''}"


def get_time_of_day_greeting() -> str:
    """
    Get appropriate greeting based on time of day.
    
    Returns:
        Greeting string (Good morning/afternoon/evening)
    """
    hour = datetime.now().hour
    
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    elif 17 <= hour < 22:
        return "Good evening"
    else:
        return "Hello"


def generate_time_context_prompt(
    last_message_time: Optional[datetime] = None,
    user_name: str = "User"
) -> str:
    """
    Generate a context prompt about time elapsed since last message.
    
    Args:
        last_message_time: Timestamp of last user message
        user_name: Name to use for the user
        
    Returns:
        Context string to add to system prompt
    """
    if not last_message_time:
        return ""
    
    elapsed = calculate_time_elapsed(last_message_time)
    elapsed_str = format_time_elapsed(elapsed)
    
    # Generate context based on elapsed time
    total_seconds = elapsed.total_seconds()
    
    if total_seconds < 300:  # Less than 5 minutes
        return f"[Context: {user_name} is actively chatting]"
    
    elif total_seconds < 3600:  # Less than 1 hour
        return f"[Context: {user_name} stepped away for {elapsed_str} and has returned]"
    
    elif total_seconds < 14400:  # Less than 4 hours
        return f"[Context: {user_name} has been away for {elapsed_str}. They may have been doing other tasks]"
    
    elif total_seconds < 86400:  # Less than 1 day
        return f"[Context: {user_name} has been gone for {elapsed_str}. Consider asking how their day went]"
    
    else:  # More than 1 day
        return f"[Context: {user_name} has been away for {elapsed_str}. Consider asking what they've been up to]"


def get_conversation_session_info(
    first_message_time: datetime,
    last_message_time: datetime
) -> Tuple[str, str]:
    """
    Get information about conversation session duration and gaps.
    
    Args:
        first_message_time: Timestamp of first message in conversation
        last_message_time: Timestamp of last message
        
    Returns:
        Tuple of (session_duration_str, last_activity_str)
    """
    session_duration = calculate_time_elapsed(first_message_time, last_message_time)
    last_activity = calculate_time_elapsed(last_message_time)
    
    return (
        format_time_elapsed(session_duration),
        format_time_elapsed(last_activity)
    )


def should_acknowledge_time_gap(elapsed: timedelta) -> bool:
    """
    Determine if the time gap is significant enough to acknowledge.
    
    Args:
        elapsed: Time elapsed since last message
        
    Returns:
        True if gap should be acknowledged
    """
    # Acknowledge gaps longer than 30 minutes
    return elapsed.total_seconds() > 1800


def get_time_context_suggestion(elapsed: timedelta) -> str:
    """
    Get a suggestion for how the bot should respond to the time gap.
    
    Args:
        elapsed: Time elapsed since last message
        
    Returns:
        Suggestion string for bot behavior
    """
    total_seconds = elapsed.total_seconds()
    
    if total_seconds < 1800:  # Less than 30 minutes
        return "Continue conversation naturally"
    
    elif total_seconds < 7200:  # Less than 2 hours
        return "Brief acknowledgment appropriate (e.g., 'Welcome back!')"
    
    elif total_seconds < 86400:  # Less than 1 day
        return "Ask about their activities (e.g., 'How was your day?')"
    
    else:  # More than 1 day
        return "Show interest in what they've been doing"


def format_timestamp_for_display(timestamp: datetime, include_date: bool = False) -> str:
    """
    Format timestamp for display in chat.
    
    Args:
        timestamp: Datetime to format
        include_date: Whether to include date
        
    Returns:
        Formatted string (e.g., "2:30 PM" or "Jan 5, 2:30 PM")
    """
    if include_date:
        return timestamp.strftime("%b %d, %I:%M %p")
    else:
        return timestamp.strftime("%I:%M %p")


def is_same_session(
    time1: datetime,
    time2: datetime,
    session_gap_minutes: int = 30
) -> bool:
    """
    Determine if two messages are in the same conversation session.
    
    Args:
        time1: First timestamp
        time2: Second timestamp
        session_gap_minutes: Minutes of inactivity that defines new session
        
    Returns:
        True if messages are in same session
    """
    gap = abs((time2 - time1).total_seconds() / 60)
    return gap <= session_gap_minutes


if __name__ == "__main__":
    # Test the time utilities
    print("=== Time Utilities Test ===\n")
    
    # Test time formatting
    test_times = [
        timedelta(seconds=30),
        timedelta(minutes=5),
        timedelta(minutes=45),
        timedelta(hours=2, minutes=30),
        timedelta(days=1),
        timedelta(days=2, hours=5),
    ]
    
    print("Time Formatting:")
    for td in test_times:
        print(f"  {td} -> {format_time_elapsed(td)}")
    
    print("\n" + "="*50 + "\n")
    
    # Test time context generation
    print("Time Context Prompts:")
    
    test_scenarios = [
        ("2 minutes ago", datetime.now() - timedelta(minutes=2)),
        ("30 minutes ago", datetime.now() - timedelta(minutes=30)),
        ("2 hours ago", datetime.now() - timedelta(hours=2)),
        ("8 hours ago", datetime.now() - timedelta(hours=8)),
        ("2 days ago", datetime.now() - timedelta(days=2)),
    ]
    
    for label, time in test_scenarios:
        context = generate_time_context_prompt(time)
        suggestion = get_time_context_suggestion(calculate_time_elapsed(time))
        print(f"\n{label}:")
        print(f"  Context: {context}")
        print(f"  Suggestion: {suggestion}")
    
    print("\n" + "="*50 + "\n")
    
    # Test time of day greeting
    print(f"Current greeting: {get_time_of_day_greeting()}")
    
    # Test timestamp display
    now = datetime.now()
    print(f"Current time: {format_timestamp_for_display(now)}")
    print(f"With date: {format_timestamp_for_display(now, include_date=True)}")
