"""Placeholder tools for the agent."""
from typing import Any


def calculator(expr: str) -> str:
    """Evaluate a math expression."""
    try:
        result = eval(expr, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def get_time() -> str:
    """Get current time."""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")


TOOLS = {
    "calculator": calculator,
    "get_time": get_time,
}
