"""
Gemini orchestration: chooses whitelisted tools only (JSON plan → execute → optional summary).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict

from agents.bq_tools import TOOL_DESCRIPTIONS, execute_tool

logger = logging.getLogger(__name__)


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty model response")
    # Strip markdown fences if present
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if m:
            text = m.group(1).strip()
    return json.loads(text)


def plan_with_gemini(user_question: str, *, model_name: str = "gemini-2.0-flash") -> Dict[str, Any]:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Set GOOGLE_API_KEY or GEMINI_API_KEY for agentic mode")

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt = f"""You are a job-market data assistant. Data lives in Google BigQuery.
You may ONLY request actions via the tools listed below. Never invent SQL.

TOOLS (JSON arguments only):
{TOOL_DESCRIPTIONS}

User question:
{user_question}

Respond with a single JSON object (no markdown), exactly one of:
{{"action":"tool","tool":"<tool_name>","arguments":{{}}}}
{{"action":"answer","text":"<brief answer if the question does not need data>"}}

If you need data, pick exactly one tool. Use empty {{}} for arguments if none required.
For top_skills, you may pass {{"limit": 10}}. For posting_volume, {{"months": 6}}.
"""
    response = model.generate_content(prompt)
    raw = (response.text or "").strip()
    logger.debug("Gemini raw: %s", raw[:500])
    return _extract_json_object(raw)


def summarize_with_gemini(
    user_question: str,
    tool_result: Dict[str, Any],
    *,
    model_name: str = "gemini-2.0-flash",
) -> str:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return json.dumps(tool_result, indent=2, default=str)

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    prompt = f"""User asked: {user_question}

Here is structured data from a trusted analytics query (JSON):
{json.dumps(tool_result, default=str)}

Give a concise, factual answer for the user (2-6 sentences). Do not suggest SQL they should run.
"""
    response = model.generate_content(prompt)
    return (response.text or "").strip()


def run_agentic_turn(
    user_question: str,
    *,
    model_name: str = "gemini-2.0-flash",
    summarize: bool = True,
) -> str:
    plan = plan_with_gemini(user_question, model_name=model_name)
    action = plan.get("action")
    if action == "answer":
        return str(plan.get("text", ""))
    if action != "tool":
        return f"Unrecognized plan from model: {plan}"

    tool_name = plan.get("tool")
    args = plan.get("arguments") or {}
    if not isinstance(args, dict):
        args = {}
    result = execute_tool(str(tool_name), args)
    if not summarize:
        return json.dumps(result, indent=2, default=str)
    if "error" in result and len(result) == 2:
        return json.dumps(result, indent=2, default=str)
    return summarize_with_gemini(user_question, result, model_name=model_name)
