"""Tests for agent tools."""
import pytest
from voice_agent.agent.tools import calculator, get_time, TOOLS


def test_calculator():
    assert calculator("2 + 2") == "4"
    assert calculator("10 * 5") == "50"
    assert "Error" in calculator("1/0")


def test_get_time():
    result = get_time()
    assert len(result) == 8
    assert ":" in result


def test_tools_registry():
    assert "calculator" in TOOLS
    assert "get_time" in TOOLS
