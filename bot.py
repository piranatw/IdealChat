import json, os, urllib.error, urllib.request

BOT_NAME = "Bot"
API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
SYSTEM = ("You are IdealChat Bot, an assistant inside a chat app. "
          "Reply in plain text, no markdown, at most 80 words.")

class BotError(Exception):
    """Message is safe to show to users."""
    
def ask_gemini(prompt, history=()):
    """history: [(role, text)] with role 'user' or 'model'. Returns the reply text."""
    if not API_KEY:
        raise BotError("Bot is not configured (no API key)")
    steps = [{"type": "user_input" if r == "user" else "model_output",
              "content": [{"type": "text", "text": t}]} for r, t in history]
    steps.append({"type": "user_input", "content": [{"type": "text", "text": prompt}]})
    body = json.dumps({"model": MODEL, "store": False,
                       "system_instruction": SYSTEM, "input": steps}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json", "x-goog-api-key": API_KEY,
        "Api-Revision": "2026-05-20"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise BotError("Bot is busy, try again in a minute" if e.code == 429
                       else f"AI service error ({e.code})")
    except (urllib.error.URLError, TimeoutError):
        raise BotError("Cannot reach the AI service")
    text = "".join(c.get("text", "") for s in data.get("steps", [])
                   if s.get("type") == "model_output"
                   for c in s.get("content", []) if c.get("type") == "text")
    if not text:
        raise BotError("The AI returned no answer")
    return text[:1000]