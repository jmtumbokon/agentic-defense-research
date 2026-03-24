"""
LLM Research Boilerplate — Dual Provider (OpenAI + Gemini)
============================================================
A 'good neighbor' script for the agentic attack & defense project.

Supports both OpenAI and Google Gemini APIs so you can switch models
without rewriting your experiment code.

Features:
  - API keys loaded from .env (never hardcoded)
  - Pinned model versions for reproducibility
  - Max iteration safety valve for agentic loops
  - Organization-level user tracking (OpenAI `user` param)
  - Per-session token usage logging with optional dry-run mode
  - Cedar enforcer hook point for policy checks inside the loop

Usage:
  Dry run (no API cost):
    python openai_research_boilerplate.py --dry-run

  Run with OpenAI (default):
    python openai_research_boilerplate.py --provider openai

  Run with Gemini:
    python openai_research_boilerplate.py --provider gemini

  Override iteration limit:
    python openai_research_boilerplate.py --max-iter 5

Intended location: ~/research/core_code/openai_research_boilerplate.py

Author:  Jayden Tumbokon
Project: Agentic Attack & Defense (OSWorld + Cedar)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ─── Load .env from project root (one level up from core_code/) ─────────────
# This lets you keep a single .env at ~/research/.env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Also check the current directory as a fallback
load_dotenv()


# ─── Configuration ───────────────────────────────────────────────────────────

# Pin model versions so results stay reproducible across runs.
# Update these deliberately when you want to test a newer snapshot.
MODELS = {
    "openai": "gpt-4o-2024-08-06",
    "gemini": "gemini-1.5-pro",
}

# Safety valve: max agentic loop iterations before the script stops.
MAX_ITERATIONS = 15  # Matches OSWorld's default max_steps

# User tag sent with OpenAI requests so the org admin can attribute usage.
USER_TAG = "Research_Assistant_Jayden"

# Paths relative to your project structure
LOG_DIR = PROJECT_ROOT / "logs"
EXPERIMENT_DIR = PROJECT_ROOT / "experiments"


# ─── Provider Abstraction ────────────────────────────────────────────────────

class OpenAIProvider:
    """Wrapper for the OpenAI Chat Completions API."""

    def __init__(self):
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            sys.exit(
                "ERROR: OPENAI_API_KEY not found in .env file.\n"
                "Add it to ~/research/.env — see env.template for format."
            )
        from openai import OpenAI
        self.client = OpenAI(api_key=key)
        self.model = MODELS["openai"]

    def complete(self, messages: list[dict]) -> dict:
        """Returns {'content': str, 'prompt_tokens': int, 'completion_tokens': int, 'total_tokens': int}"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            user=USER_TAG,
        )
        usage = response.usage
        return {
            "content": response.choices[0].message.content,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }


class GeminiProvider:
    """Wrapper for the Google Generative AI (Gemini) API."""

    def __init__(self):
        key = os.getenv("GENAI_API_KEY")
        if not key:
            sys.exit(
                "ERROR: GENAI_API_KEY not found in .env file.\n"
                "Add it to ~/research/.env — see env.template for format."
            )
        import google.generativeai as genai
        genai.configure(api_key=key)
        self.model = genai.GenerativeModel(MODELS["gemini"])

    def complete(self, messages: list[dict]) -> dict:
        """
        Converts OpenAI-style messages to Gemini format and returns
        the same dict shape as OpenAIProvider.complete().
        """
        # Gemini uses 'user'/'model' roles instead of 'user'/'assistant'.
        # System messages get prepended to the first user message.
        system_parts = []
        gemini_history = []

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "system":
                system_parts.append(content)
            elif role == "user":
                # Prepend any accumulated system text to the first user msg
                if system_parts:
                    content = "\n\n".join(system_parts) + "\n\n" + content
                    system_parts = []
                gemini_history.append({"role": "user", "parts": [content]})
            elif role == "assistant":
                gemini_history.append({"role": "model", "parts": [content]})

        chat = self.model.start_chat(history=gemini_history[:-1])
        last_user_msg = gemini_history[-1]["parts"][0]
        response = chat.send_message(last_user_msg)

        # Gemini token counting
        prompt_tokens = response.usage_metadata.prompt_token_count
        completion_tokens = response.usage_metadata.candidates_token_count
        return {
            "content": response.text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }


def get_provider(name: str):
    """Factory: returns the right provider instance."""
    if name == "openai":
        return OpenAIProvider()
    elif name == "gemini":
        return GeminiProvider()
    else:
        sys.exit(f"ERROR: Unknown provider '{name}'. Use 'openai' or 'gemini'.")


# ─── Token Tracker ───────────────────────────────────────────────────────────

class TokenTracker:
    """Accumulates token counts across multiple API calls in one session."""

    def __init__(self, provider_name: str, model: str):
        self.provider_name = provider_name
        self.model = model
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.call_count = 0

    def record(self, usage: dict):
        """Record usage from a single API response dict."""
        self.prompt_tokens += usage["prompt_tokens"]
        self.completion_tokens += usage["completion_tokens"]
        self.total_tokens += usage["total_tokens"]
        self.call_count += 1

    def summary(self) -> str:
        return (
            f"Session token summary ({self.provider_name} / {self.model})\n"
            f"  API calls:         {self.call_count}\n"
            f"  Prompt tokens:     {self.prompt_tokens:,}\n"
            f"  Completion tokens: {self.completion_tokens:,}\n"
            f"  Total tokens:      {self.total_tokens:,}"
        )

    def to_dict(self) -> dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "provider": self.provider_name,
            "model": self.model,
            "api_calls": self.call_count,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


# ─── Cedar Enforcer Hook ────────────────────────────────────────────────────
# Uncomment and adapt once you integrate cedar_enforcer.py into the loop.
#
# from cedar_enforcer import CedarEnforcer
#
# CEDAR_POLICY_DIR = PROJECT_ROOT / "cedar_policies"
# enforcer = CedarEnforcer(
#     policy_file=str(CEDAR_POLICY_DIR / "agent_policy.cedar"),
#     entities_file=str(CEDAR_POLICY_DIR / "agent_entities.json"),
# )
#
# def check_with_cedar(action_string: str) -> bool:
#     """Returns True if the action is ALLOWED, False if BLOCKED."""
#     result = enforcer.check_action(action_string)
#     return result == "ALLOWED"


# ─── Core Functions ──────────────────────────────────────────────────────────

def single_completion(
    provider,
    messages: list[dict],
    tracker: TokenTracker,
    dry_run: bool = False,
) -> str | None:
    """
    Send one chat-completion request and return the assistant's reply.

    In dry-run mode, prints the request payload without calling the API.
    """
    if dry_run:
        print("[DRY RUN] Would send the following request:")
        print(f"  Provider: {tracker.provider_name}")
        print(f"  Model:    {tracker.model}")
        print(f"  Messages ({len(messages)}):")
        for msg in messages:
            role = msg["role"]
            preview = msg["content"][:80] + ("..." if len(msg["content"]) > 80 else "")
            print(f"    [{role}] {preview}")
        return None

    result = provider.complete(messages)
    tracker.record(result)
    return result["content"]


def agentic_loop(
    provider,
    initial_prompt: str,
    tracker: TokenTracker,
    dry_run: bool = False,
    max_iterations: int = MAX_ITERATIONS,
) -> list[str]:
    """
    Run an agentic loop where each iteration feeds the model's previous
    output back in. A safety valve stops execution after max_iterations.

    CEDAR INTEGRATION POINT:
    After the model returns a reply containing an action, you would:
      1. Parse the action:   parsed = enforcer.parse_agent_action(reply)
      2. Check the policy:   allowed = enforcer.check_action(parsed)
      3. If blocked, skip execution and tell the model it was denied.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a research assistant helping with agentic AI safety experiments. "
                "When the task is complete, respond with exactly: TASK_COMPLETE"
            ),
        },
        {"role": "user", "content": initial_prompt},
    ]

    results = []

    for i in range(1, max_iterations + 1):
        print(f"\n--- Iteration {i}/{max_iterations} ---")

        reply = single_completion(provider, messages, tracker, dry_run=dry_run)

        if dry_run:
            print("[DRY RUN] Stopping after first iteration preview.")
            break

        print(f"Assistant: {reply[:200]}{'...' if len(reply) > 200 else ''}")
        results.append(reply)

        # ── Cedar policy check would go here ─────────────────────────────
        # if not check_with_cedar(reply):
        #     print("CEDAR BLOCKED this action.")
        #     messages.append({"role": "assistant", "content": reply})
        #     messages.append({
        #         "role": "user",
        #         "content": "That action was denied by security policy. Try a different approach.",
        #     })
        #     continue

        # ── Stopping criteria ────────────────────────────────────────────
        if "TASK_COMPLETE" in reply:
            print("Agent signaled completion.")
            break

        # Feed the reply back for the next iteration
        messages.append({"role": "assistant", "content": reply})
        messages.append(
            {
                "role": "user",
                "content": "Continue with the next step, or say TASK_COMPLETE if done.",
            }
        )
    else:
        print(
            f"\nSAFETY VALVE: Reached {max_iterations} iterations. "
            "Stopping to prevent runaway costs."
        )

    return results


def save_usage_log(tracker: TokenTracker):
    """Append the session's token usage to a JSON-Lines log file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "usage_log.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(tracker.to_dict()) + "\n")
    print(f"Usage log appended to {log_path}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="LLM research boilerplate with safety guardrails."
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "gemini"],
        default="openai",
        help="Which LLM provider to use (default: openai).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the request without calling the API (no cost incurred).",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=MAX_ITERATIONS,
        help=f"Override the max iteration safety valve (default: {MAX_ITERATIONS}).",
    )
    args = parser.parse_args()

    provider = get_provider(args.provider)
    model = MODELS[args.provider]
    tracker = TokenTracker(provider_name=args.provider, model=model)

    # ── Example: single completion ────────────────────────────────────────
    print("=" * 60)
    print(f"Single completion demo  [{args.provider} / {model}]")
    print("=" * 60)

    reply = single_completion(
        provider,
        messages=[
            {"role": "system", "content": "You are a helpful research assistant."},
            {"role": "user", "content": "Summarize what Cedar policies do in one sentence."},
        ],
        tracker=tracker,
        dry_run=args.dry_run,
    )
    if reply:
        print(f"Reply: {reply}")

    # ── Example: agentic loop ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"Agentic loop demo  [{args.provider} / {model}]")
    print("=" * 60)

    agentic_loop(
        provider,
        initial_prompt=(
            "List 3 potential attack scenarios for an AI agent operating "
            "a desktop computer, then say TASK_COMPLETE."
        ),
        tracker=tracker,
        dry_run=args.dry_run,
        max_iterations=args.max_iter,
    )

    # ── Session summary ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(tracker.summary())
    print("=" * 60)

    if not args.dry_run:
        save_usage_log(tracker)


if __name__ == "__main__":
    main()
