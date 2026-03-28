"""
DIS-1 smoke test: verify Claude API connectivity.

Sends a simple message to Claude Sonnet and checks that a valid response
comes back. This confirms the ANTHROPIC_API_KEY is set and the API is reachable.

Run:  source .venv/bin/activate && python test_claude_api.py
Requires: ANTHROPIC_API_KEY set in .env or environment.
"""

import os
import sys

from dotenv import load_dotenv
import anthropic

load_dotenv()


def test_claude_api():
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
    test_claude_api()
