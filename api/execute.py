#!/usr/bin/env python3
"""
Omega API Handler - Vercel Serverless Function
Provides HTTP endpoint for executing AI agent goals
"""

import json
import os
import sys
import textwrap
import traceback
from typing import Dict, Any

def _ensure(pkg: str, import_as: str | None = None):
    """Bootstrap missing dependencies."""
    import importlib
    name = import_as or pkg
    try:
        importlib.import_module(name)
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

_ensure("google-generativeai", "google.generativeai")
_ensure("requests")

import google.generativeai as genai

SYSTEM_PROMPT = textwrap.dedent("""
You are OMEGA — an elite autonomous AI agent.

CORE DIRECTIVES:
1. REASON first, then ACT. Always emit a JSON block: {"thought": "...", "action": "...", "action_input": "..."}
2. Available actions: finish (end the task)
3. Be concise and helpful.
4. Return valid JSON only.
""").strip()

def init_gemini():
    """Initialize Gemini client."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )

def parse_action_block(text: str) -> Dict[str, Any] | None:
    """Extract JSON action block from model response."""
    import re
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*?\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None

def react_loop(model, goal: str, max_iterations: int = 5) -> Dict[str, Any]:
    """Execute ReAct loop and return results."""
    chat = model.start_chat(history=[])
    messages = [f"GOAL: {goal}\n\nRespond with ONLY a JSON action block. When done, use action='finish'."]
    log = []
    
    for iteration in range(1, max_iterations + 1):
        try:
            response = chat.send_message(messages[-1])
            reply = response.text.strip()
        except Exception as e:
            log.append({
                "type": "error",
                "iteration": iteration,
                "content": f"Gemini API error: {str(e)}"
            })
            continue
        
        block = parse_action_block(reply)
        if not block:
            log.append({
                "type": "error",
                "iteration": iteration,
                "content": "Invalid JSON response"
            })
            continue
        
        thought = block.get("thought", "")
        action = block.get("action", "").lower()
        action_input = block.get("action_input", "")
        
        log.append({
            "type": "iteration",
            "iteration": iteration,
            "thought": thought,
            "action": action,
            "action_input": str(action_input)[:100]
        })
        
        if action == "finish":
            log.append({
                "type": "success",
                "content": str(action_input)
            })
            return {
                "status": "success",
                "iterations": iteration,
                "log": log,
                "summary": str(action_input)
            }
        
        observation = f"OBSERVATION: Action '{action}' processed. Continue your ReAct loop or finish."
        log.append({"type": "observation", "content": observation})
        messages.append(f"{reply}\n\n{observation}\n\nEmit next action as JSON.")
    
    return {
        "status": "max_iterations",
        "iterations": max_iterations,
        "log": log,
        "summary": "Reached maximum iterations"
    }

def handler(request):
    """
    Vercel Serverless Function Handler
    POST /api/execute with {"goal": "your goal"}
    """
    # CORS headers
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
    
    # Handle CORS preflight
    if request.method == "OPTIONS":
        return (json.dumps({"ok": True}), 200, headers)
    
    if request.method != "POST":
        return (json.dumps({"error": "Method not allowed"}), 405, headers)
    
    try:
        body = json.loads(request.body or "{}")
        goal = body.get("goal", "").strip()
        
        if not goal:
            return (
                json.dumps({"error": "Missing 'goal' in request body"}),
                400,
                headers
            )
        
        model = init_gemini()
        result = react_loop(model, goal)
        
        return (json.dumps(result), 200, headers)
    
    except ValueError as e:
        return (
            json.dumps({"error": str(e)}),
            400,
            headers
        )
    except Exception as e:
        return (
            json.dumps({"error": f"Internal server error: {str(e)}"}),
            500,
            headers
        )
