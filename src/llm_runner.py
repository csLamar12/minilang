"""
llm_runner.py — LLM integration for the MiniLang Compiler
CIT4004 · University of Technology, Jamaica

Uses the Google Gemini API (free tier — no credit card required).
Requires:
    pip install google-genai

Get a FREE API key at https://aistudio.google.com/app/apikey
Then save it via Tools -> Settings in the MiniLang app.
"""

import os

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert teaching assistant for MiniLang, a small educational
programming language used in the CIT4004 Analysis of Programming Languages
course at the University of Technology, Jamaica.

MiniLang quick reference
------------------------
Variables    : let x = value        (declare + initialise)
               x = newValue         (reassign)
Output       : display expr1 expr2 ...
Conditionals : if condition
                   statements
               else
                   statements
               end
While loop   : while condition
                   statements
               end
For loop     : for var = start to end step n
                   statements
               end
Try/catch    : try
                   statements
               catch
                   statements
               end
Blocks       : begin  statements  end
Break        : break  (exits the nearest loop)
Comments     : -- this is a comment
Types        : integers, floats, strings ("..."), booleans (true/false)
Operators    : + - * / %   == != < > <= >=   and  or  not

Guidelines
----------
- Be concise and student-friendly.
- Explain concepts clearly; avoid jargon unless you define it.
- When you show corrected or example code, use the exact MiniLang syntax above.
- If the user asks something unrelated to programming or MiniLang, politely
  redirect them.
"""

# ── Model config ──────────────────────────────────────────────────────────────

DEFAULT_MODEL = "gemini-2.5-flash"  # free tier — smarter, needs >=512 tokens for thinking step
MAX_TOKENS    = 2048               # 2.5-flash uses some tokens for internal reasoning


# ── Setup check ───────────────────────────────────────────────────────────────

def _check_setup() -> "str | None":
    """Return an error string if the google-genai SDK or API key is missing."""
    try:
        from google import genai  # noqa: F401
    except ImportError:
        return (
            "❌  The 'google-genai' Python package is not installed.\n\n"
            "Fix:\n"
            "    pip install google-genai\n\n"
            "Then get a free API key at: https://aistudio.google.com/app/apikey\n"
            "and save it via  Tools -> Settings  in the MiniLang app."
        )
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        return (
            "❌  No Google API key found.\n\n"
            "Fix:\n"
            "  1. Go to  https://aistudio.google.com/app/apikey\n"
            "  2. Sign in with a free Google account\n"
            "  3. Click 'Create API Key'\n"
            "  4. Paste the key via  Tools -> Settings  in the MiniLang app.\n\n"
            "The Gemini free tier gives you 1,500 requests/day — no credit card needed."
        )
    return None


def api_available() -> bool:
    """Return True if the SDK is installed and a Google API key is set."""
    return _check_setup() is None


# ── Error helper ──────────────────────────────────────────────────────────────

def _http_status(exc: Exception) -> "int | None":
    """
    Try to extract an HTTP status code from any exception type.
    Works with google.genai errors, httpx, requests, etc.
    """
    for attr in ("status_code", "code"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    # Some SDKs nest the response object
    resp = getattr(exc, "response", None)
    if resp is not None:
        for attr in ("status_code", "status"):
            val = getattr(resp, attr, None)
            if isinstance(val, int):
                return val
    return None


def _friendly_error(exc: Exception) -> str:
    """Convert an API exception into a human-readable string."""
    status = _http_status(exc)
    msg    = str(exc).lower()

    if status == 429 or "quota" in msg or "rate limit" in msg or "resource exhausted" in msg:
        return (
            "❌  Rate limit reached (free tier: 15 requests/minute).\n"
            "Please wait a moment and try again."
        )
    if status in (401, 403) or "api key" in msg or "permission denied" in msg or "invalid api key" in msg:
        return (
            "❌  API key rejected by Google.\n"
            "Double-check your key via  Tools -> Settings."
        )
    if status is not None and status >= 500 or "server error" in msg or "internal" in msg:
        return "❌  Google AI server error. Please try again in a few seconds."
    if any(k in msg for k in ("connect", "network", "timeout", "unreachable", "name or service")):
        return "❌  Could not connect to Google AI. Check your internet connection."
    if "safety" in msg or "blocked" in msg or "finish_reason" in msg:
        return "❌  Response blocked by Google's safety filters. Try rephrasing."

    # Fall-through: show the raw error so the user can diagnose it
    return f"❌  Unexpected error ({type(exc).__name__}): {exc}"


# ── Public API ────────────────────────────────────────────────────────────────

def get_ai_response(
    prompt: str,
    *,
    code: str  = "",
    error: str = "",
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Send *prompt* to Gemini and return the response as a plain string.

    Args:
        prompt: The user's question or instruction.
        code:   (optional) MiniLang source code to include as context.
        error:  (optional) Error text to include as context.
        model:  Gemini model name (default: gemini-2.0-flash-lite).

    Returns:
        The AI's reply, or a human-readable error message string.
    """
    setup_err = _check_setup()
    if setup_err:
        return setup_err

    from google import genai
    from google.genai import types

    # Build the user message
    parts: list[str] = []
    if code.strip():
        parts.append(f"MiniLang code:\n```\n{code.strip()}\n```")
    if error.strip():
        parts.append(f"Error message(s):\n{error.strip()}")
    parts.append(prompt)
    user_message = "\n\n".join(parts)

    try:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

        response = client.models.generate_content(
            model=model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                max_output_tokens=MAX_TOKENS,
            ),
        )
        return response.text

    except Exception as exc:
        return _friendly_error(exc)


# ── Convenience wrappers ──────────────────────────────────────────────────────

def explain_code(code: str) -> str:
    """Explain what a MiniLang program does, step by step."""
    return get_ai_response(
        "Explain what this MiniLang program does, step by step. "
        "Be concise and suitable for a first-year student.",
        code=code,
    )


def explain_errors(code: str, errors: str) -> str:
    """Explain one or more compiler errors in plain language."""
    return get_ai_response(
        "Explain these errors in plain language and tell me exactly "
        "how to fix each one. Show corrected code if helpful.",
        code=code,
        error=errors,
    )


def suggest_fix(code: str, errors: str) -> str:
    """Return a corrected version of the code with an explanation."""
    return get_ai_response(
        "Fix all the errors in this MiniLang code. "
        "Show the complete corrected program and briefly explain every change.",
        code=code,
        error=errors,
    )


def ask(question: str, code: str = "") -> str:
    """Answer an arbitrary question about MiniLang or the given code."""
    return get_ai_response(question, code=code)


# ── CLI smoke-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("MiniLang LLM Runner — quick test (Google Gemini)")
    print(f"API available: {api_available()}")
    if api_available():
        resp = ask("What is MiniLang and what is it used for?")
        print("\n--- Response ---")
        print(resp)
