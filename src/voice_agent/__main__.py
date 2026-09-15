"""Allow: python -m voice_agent"""
from .main import main
import sys
import asyncio

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
