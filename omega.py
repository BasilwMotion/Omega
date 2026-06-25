"""
OMEGA — Autonomous AI Agent Core Engine
ReAct Loop | Self-Modification | Web Fetch | Voice Commands
Powered by Google Gemini API (free tier)
"""

import os
import sys
import json
import time
import textwrap
import traceback
import urllib.request
import urllib.error
import re
from pathlib import Path
from datetime import datetime

# ── Dependency bootstrap ────────────────────────────────────────────────────
def _ensure(pkg: str, import_as: str | None = None):
    import importlib
    name = import_as or pkg
    try:
        importlib.import_module(name)
    except ImportError:
        import subprocess
        print(f"[OMEGA] Installing missing dependency: {pkg}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

_ensure("google-generativeai", "google.generativeai")
_ensure("requests")
_ensure("SpeechRecognition", "speech_recognition")

try:
    _ensure("pyaudio")
except Exception:
    print("[OMEGA] pyaudio optional — voice input may be limited on this system.")

import google.generativeai as genai
import requests
import speech_recognition as sr

# ── Configuration ────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).parent
GEMINI_MODEL = "gemini-1.5-flash"          # free-tier model
MAX_LOOP_ITERATIONS = 20
OMEGA_LOG = WORKSPACE / "omega_log.jsonl"

SYSTEM_PROMPT = textwrap.dedent("""
You are OMEGA — an elite autonomous AI agent and principal systems engineer.

CORE DIRECTIVES:
1. REASON first, then ACT. Always emit a JSON block structured as:
   {"thought": "...", "action": "...", "action_input": "..."}
2. Available actions:
   - read_file      : Read a file. action_input = relative file path
   - write_file     : Overwrite a file. action_input = {"path": "...", "content": "..."}
   - web_fetch      : Fetch a URL. action_input = URL string
   - shell_safe     : Run a safe read-only shell command (dir/ls/python --version).
                      action_input = command string
   - finish         : End the loop. action_input = final summary string
3. CODE QUALITY RULES (non-negotiable):
   - Use defensive programming: validate inputs, handle all exceptions explicitly.
   - Prefer algorithmic clarity over cleverness.
   - No dead code, no TODO comments, no placeholder stubs.
   - Every function must have a docstring and type hints.
   - DRY principle enforced — extract repeated logic into named helpers.
4. SELF-MODIFICATION:
   - You may read and rewrite any file in your workspace, including yourself.
   - Before writing, always read the existing file first to preserve intent.
   - Append a one-line comment at the top of modified files: # OMEGA-MODIFIED: <timestamp>
5. Always return valid JSON for your action block. No markdown fences.
""").strip()

# ── Gemini client ────────────────────────────────────────────────────────────
def init_gemini() -> genai.GenerativeModel:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        key_file = WORKSPACE / "gemini_key.txt"
        if key_file.exists():
            api_key = key_file.read_text().strip()
    if not api_key:
        api_key = input("[OMEGA] Enter your Gemini API key: ").strip()
        (WORKSPACE / "gemini_key.txt").write_text(api_key)
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )
    print(f"[OMEGA] Gemini model ready: {GEMINI_MODEL}")
    return model

# ── Action handlers ──────────────────────────────────────────────────────────
def action_read_file(path: str) -> str:
    target = (WORKSPACE / path).resolve()
    if not str(target).startswith(str(WORKSPACE)):
        return "ERROR: Path escapes workspace boundary."
    if not target.exists():
        return f"ERROR: File not found: {path}"
    return target.read_text(encoding="utf-8")


def action_write_file(raw: str | dict) -> str:
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return "ERROR: write_file requires JSON with 'path' and 'content'."
    else:
        data = raw

    path = data.get("path", "")
    content = data.get("content", "")
    target = (WORKSPACE / path).resolve()

    if not str(target).startswith(str(WORKSPACE)):
        return "ERROR: Path escapes workspace boundary."

    target.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    header = f"# OMEGA-MODIFIED: {timestamp}\n"

    text_extensions = {".py", ".js", ".ts", ".html", ".css", ".json", ".txt", ".md"}
    if target.suffix in text_extensions and not content.startswith("# OMEGA-MODIFIED"):
        content = header + content

    target.write_text(content, encoding="utf-8")
    return f"OK: Written {len(content)} chars to {path}"


def action_web_fetch(url: str) -> str:
    try:
        headers = {"User-Agent": "OmegaAgent/1.0 (research)"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read(32_768).decode("utf-8", errors="replace")
        # Strip HTML tags for cleaner context
        clean = re.sub(r"<[^>]+>", " ", raw)
        clean = re.sub(r"\s{2,}", " ", clean).strip()
        return clean[:8000]
    except urllib.error.URLError as e:
        return f"ERROR fetching {url}: {e.reason}"
    except Exception as e:
        return f"ERROR: {e}"


def action_shell_safe(command: str) -> str:
    import subprocess
    ALLOWED = {"dir", "ls", "python", "node", "npm", "pip", "echo", "type", "cat"}
    cmd_root = command.strip().split()[0].lower()
    if cmd_root not in ALLOWED:
        return f"ERROR: Command '{cmd_root}' is not in the safe-list."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=15
        )
        return (result.stdout + result.stderr).strip()[:4000]
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out."
    except Exception as e:
        return f"ERROR: {e}"


ACTIONS = {
    "read_file": action_read_file,
    "write_file": action_write_file,
    "web_fetch": action_web_fetch,
    "shell_safe": action_shell_safe,
}

# ── ReAct execution loop ─────────────────────────────────────────────────────
def parse_action_block(text: str) -> dict | None:
    text = text.strip()
    # Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract first JSON object from mixed text
    match = re.search(r"\{[\s\S]*?\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def log_event(entry: dict):
    with OMEGA_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def react_loop(model: genai.GenerativeModel, goal: str):
    print(f"\n[OMEGA] Goal accepted: {goal}\n{'─'*60}")
    chat = model.start_chat(history=[])
    messages = [f"GOAL: {goal}\n\nBegin your ReAct loop. Emit only a JSON action block."]

    for iteration in range(1, MAX_LOOP_ITERATIONS + 1):
        print(f"\n[OMEGA] ── Iteration {iteration} ──")
        prompt = messages[-1]

        try:
            response = chat.send_message(prompt)
            reply = response.text.strip()
        except Exception as e:
            print(f"[OMEGA] Gemini error: {e}")
            time.sleep(5)
            continue

        print(f"[OMEGA] Model reply:\n{reply}\n")
        block = parse_action_block(reply)

        if not block:
            msg = "OBSERVATION: Could not parse JSON action block. Please emit valid JSON only."
            messages.append(msg)
            continue

        thought = block.get("thought", "")
        action = block.get("action", "").lower()
        action_input = block.get("action_input", "")

        if thought:
            print(f"[OMEGA] Thought: {thought}")

        log_event({
            "ts": datetime.now().isoformat(),
            "iteration": iteration,
            "thought": thought,
            "action": action,
            "action_input": str(action_input)[:200],
        })

        if action == "finish":
            print(f"\n[OMEGA] ✓ Task complete:\n{action_input}")
            log_event({"ts": datetime.now().isoformat(), "status": "finished", "summary": action_input})
            return

        handler_fn = ACTIONS.get(action)
        if not handler_fn:
            observation = f"OBSERVATION: Unknown action '{action}'. Valid: {list(ACTIONS.keys())} or 'finish'."
        else:
            try:
                observation = f"OBSERVATION: {handler_fn(action_input)}"
            except Exception as e:
                observation = f"OBSERVATION: Action raised exception: {traceback.format_exc()}"

        print(f"[OMEGA] {observation[:300]}")
        messages.append(f"{reply}\n\n{observation}\n\nContinue your ReAct loop.")

    print("[OMEGA] Max iterations reached. Loop terminated.")

# ── Voice input engine ───────────────────────────────────────────────────────
def listen_for_command(timeout: int = 8) -> str | None:
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    try:
        with sr.Microphone() as source:
            print("[OMEGA] Listening for voice command... (speak now)")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=20)
        text = recognizer.recognize_google(audio)
        print(f"[OMEGA] Voice captured: \"{text}\"")
        return text
    except sr.WaitTimeoutError:
        print("[OMEGA] No speech detected within timeout.")
        return None
    except sr.UnknownValueError:
        print("[OMEGA] Speech not understood — please try again.")
        return None
    except sr.RequestError as e:
        print(f"[OMEGA] Speech service error: {e}")
        return None
    except OSError:
        print("[OMEGA] Microphone unavailable — falling back to text input.")
        return None

# ── Main entrypoint ──────────────────────────────────────────────────────────
def main():
    print(textwrap.dedent("""
    ╔══════════════════════════════════════════════════╗
    ║           OMEGA — Autonomous AI Agent            ║
    ║      ReAct | Self-Modify | Web | Voice           ║
    ╚══════════════════════════════════════════════════╝
    """))

    model = init_gemini()

    while True:
        print("\n[OMEGA] Input mode:")
        print("  1 — Type a goal")
        print("  2 — Speak a goal (voice)")
        print("  3 — Exit")
        choice = input("Select [1/2/3]: ").strip()

        if choice == "3":
            print("[OMEGA] Shutting down. Goodbye.")
            break
        elif choice == "2":
            goal = listen_for_command()
            if not goal:
                continue
        else:
            goal = input("[OMEGA] Enter goal: ").strip()
            if not goal:
                continue

        react_loop(model, goal)


if __name__ == "__main__":
    main()
