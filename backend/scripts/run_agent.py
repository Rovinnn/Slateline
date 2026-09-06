"""Drive the ADK agent from the command line.

    python scripts/run_agent.py "We have a $2M drama shooting 22 days out of
                                 LA with 45 crew. Georgia or New Mexico?"

Needs the same credentials as the rest of Layer 1 — Vertex AI (for the agent's
own reasoning and for extraction) plus a Parallel key. Run
`scripts/check_credentials.py` first if anything here fails; a missing ADC is
by far the likeliest cause.

This exists so the agent is runnable rather than merely declared. The REST API
in app/main.py is unchanged and is still what the deployed frontend uses — see
app/agent/agent.py for why this is deliberately additive.

Every tool call is printed as it happens, which is the interesting part: you
can watch the agent decide to search a jurisdiction, fetch its distance, call
the calculator, and challenge the leader before recommending it. If you ever
see it state a figure that didn't come out of a tool result printed above, the
instruction in agent.py has failed and that's a bug worth reporting.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent import root_agent
from app.agent import session as agent_session

APP_NAME = "incentive_verifier"
DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"


async def ask(prompt: str) -> None:
    session_service = InMemorySessionService()
    user_id, session_id = "cli", uuid.uuid4().hex[:12]
    await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)

    runner = Runner(app_name=APP_NAME, agent=root_agent, session_service=session_service)
    message = types.Content(role="user", parts=[types.Part(text=prompt)])

    print(f"{BOLD}you:{RESET} {prompt}\n")
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
        for part in getattr(event.content, "parts", None) or []:
            if part.function_call is not None:
                args = ", ".join(f"{k}={v!r}" for k, v in (part.function_call.args or {}).items())
                print(f"{DIM}  -> {part.function_call.name}({args}){RESET}")
            elif part.function_response is not None:
                # Truncated: a full breakdown is long, and what matters here is
                # seeing that the number came from a tool at all.
                body = str(part.function_response.response)
                print(f"{DIM}  <- {body[:220]}{'...' if len(body) > 220 else ''}{RESET}")
            elif part.text:
                print(f"\n{BOLD}agent:{RESET} {part.text.strip()}\n")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    agent_session.clear()
    try:
        asyncio.run(ask(" ".join(sys.argv[1:])))
    except Exception as exc:  # noqa: BLE001 - a CLI should explain, not traceback
        print(f"\nagent run failed: {type(exc).__name__}: {exc}")
        print("If this mentions credentials, run scripts/check_credentials.py.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
