"""ADK agent over the existing three-layer pipeline.

Additive: app/main.py and the REST pipeline are untouched, so nothing here can
break the deployed product. See agent.py for what this adds and what it
deliberately doesn't.
"""

from .agent import root_agent

__all__ = ["root_agent"]
