"""
File: tests/manual/test_claude_api.py
Owner: Likitha Shankar
Description: Minimal Anthropic SDK smoke test — sends a one-line prompt to
  claude-sonnet-4-20250514 and asserts the reply contains “DischargeIQ” to verify
  API key and network path before heavier pipeline runs.
Key functions/classes: run_claude_api_smoke
Edge cases handled:
  - Exits with message on missing key; catches auth and connection errors explicitly.
Dependencies: anthropic, dotenv
Called by: Manual: ``python tests/manual/test_claude_api.py`` from repo root.
"""

import os
import sys

from dotenv import load_dotenv
import anthropic

load_dotenv()


def run_claude_api_smoke():
    """
    Send a single message to Claude and verify the response contains expected text.

    Raises:
        anthropic.AuthenticationError: If the API key is missing or invalid.
        AssertionError: If the response does not contain the expected string.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set. Add it to .env and try again.")
        sys.exit(1)

    try:
        client = anthropic.Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": "Reply with exactly: DischargeIQ API test passed",
                }
            ],
        )

        output = response.content[0].text.strip()
        print(f"Claude response: {output}")

        assert "DischargeIQ" in output, f"Unexpected response: {output}"
        print("Claude API test PASSED")

    except anthropic.AuthenticationError as auth_error:
        print(f"Authentication failed — check your ANTHROPIC_API_KEY: {auth_error}")
        sys.exit(1)
    except anthropic.APIConnectionError as conn_error:
        print(f"Could not reach the Anthropic API: {conn_error}")
        sys.exit(1)


if __name__ == "__main__":
    run_claude_api_smoke()
