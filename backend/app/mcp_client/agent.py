import json
import os
import logging
from typing import Any, Dict, List, Optional
import sys

import subprocess

from dotenv import dotenv_values

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.exceptions import ToolError

from app.llm.factory import get_llm


logger = logging.getLogger(__name__)

# ── System prompt ────────────────────────────────────────────────────────────
# We give the LLM the real tool list (fetched live from MCP server) and ask
# it to return BOTH the tool name AND the arguments in one JSON response.
# This avoids a second LLM round trip just to extract arguments.

DECISION_PROMPT = """You are an intelligent ERP assistant connected to Odoo via MCP tools.

Available tools:
{tools}

When the user sends a message, decide:
1. Which tool fits best (use the exact tool name from the list above)
2. What arguments to pass to it (based on the tool's parameter descriptions)

Respond with ONLY valid JSON — no explanation, no markdown, no extra text:

If a tool is needed:
{{
    "tool": "exact_tool_name",
    "args": {{
        "param_name": "value"
    }},
    "reason": "one sentence why"
}}

If no tool matches the request:
{{
    "tool": "none",
    "args": {{}},
    "reason": "one sentence why no tool fits"
}}

Rules:
- Use ONLY tool names from the list above. Never invent tool names.
- If the user is just chatting, asking a general question, or the request
  does not match any tool, return "tool": "none".
- For invoice_payload arguments, build the JSON string from what the user said.
"""

RESPONSE_PROMPT = """You are a professional ERP assistant. 
Given the user's message and the tool result below, write a clear, 
helpful response. Be concise. Do not expose internal IDs or raw JSON 
unless the user specifically asked for them."""
import subprocess


class Agent:
    
    def __init__(self):
        self.llm = get_llm()

        _here = os.path.dirname(os.path.abspath(__file__))
        _default_mcp_path = os.path.abspath(
            os.path.join(_here, "..", "..", "..", "mcp-erp-server")
        )
        _env_path = os.path.abspath(
            os.path.join(_here, "..", "..", ".env")
        )
        _env = dotenv_values(_env_path)
        mcp_server_path = _env.get("MCP_SERVER_PATH") or _default_mcp_path

        logger.info("MCP server path: %s", mcp_server_path)
        logger.info("main.py exists: %s",
                    os.path.exists(os.path.join(mcp_server_path, "main.py")))

        # ── Key fix: start with the FULL current environment ──────────
        # then add Odoo vars on top. This is exactly what your terminal
        # has when you run main.py manually and it works.
        subprocess_env = {**os.environ}
        subprocess_env["ODOO_URL"]    = _env.get("ODOO_URL", "")
        subprocess_env["ODOO_DB"]     = _env.get("ODOO_DB", "")
        subprocess_env["ODOO_API_KEY"] = _env.get("ODOO_API_KEY", "")
        subprocess_env["PYTHONPATH"]  = mcp_server_path
        subprocess_env["PYTHONIOENCODING"] = "utf-8"
        subprocess_env["PYTHONUTF8"]  = "1"
        self._debug_subprocess(mcp_server_path)
        self._transport = StdioTransport(
            command=sys.executable,
            args=["main.py"],
            cwd=mcp_server_path,
            env=subprocess_env,
        )

    def _debug_subprocess(self, mcp_server_path: str) -> None:
      """Runs main.py for 3 seconds and captures all output."""
      import time

      proc = subprocess.Popen(
          [sys.executable, "main.py"],
          cwd=mcp_server_path,
          env={
            **os.environ,
            "ODOO_URL": os.environ.get("ODOO_URL", ""),
            "ODOO_DB": os.environ.get("ODOO_DB", ""),
            "ODOO_API_KEY": os.environ.get("ODOO_API_KEY", ""),
            "PYTHONPATH": mcp_server_path,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
          },
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
        )

      try:
            stdout, stderr = proc.communicate(timeout=3)
      except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            logger.info("Subprocess ran for 3s without crashing — process works")

            logger.error("Subprocess exited with code %d", proc.returncode)
            logger.error("STDOUT: %s", stdout.decode("utf-8", errors="replace"))
            logger.error("STDERR: %s", stderr.decode("utf-8", errors="replace"))
    # ── Public entry point ───────────────────────────────────────────────────

    async def run(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        history = history or []

        # Step 1 — fetch real tool list from MCP server
        tools_description = await self._fetch_tools_description()

        # Step 2 — ask LLM to decide tool + arguments
        decision = await self._decide(user_message, history, tools_description)
        tool_name = decision.get("tool")
        tool_args = decision.get("args", {})

        logger.info("Tool decision: tool=%s reason=%s", tool_name, decision.get("reason"))

        # Step 3 — handle "no tool" case
        if not tool_name or tool_name == "none":
            return await self._respond(user_message, history, tool_result=None)

        # Step 4 — check the tool actually exists on the MCP server
        known_tools = await self._fetch_tool_names()
        if tool_name not in known_tools:
            logger.warning("LLM chose unknown tool: %s", tool_name)
            return (
                f"I couldn't find a tool called '{tool_name}'. "
                f"Available tools are: {', '.join(known_tools)}. "
                f"Please rephrase your request."
            )

        # Step 5 — call the tool on the MCP server
        tool_result = await self._call_tool(tool_name, tool_args)

        # Step 6 — format final response
        return await self._respond(user_message, history, tool_result)

    # ── MCP client helpers ───────────────────────────────────────────────────

    async def _fetch_tools_description(self) -> str:
        """
        Opens a short-lived MCP connection, lists all tools with their
        descriptions and parameter schemas, returns a formatted string
        for the LLM system prompt.
        """
        try:
            async with Client(self._transport) as client:
                tools = await client.list_tools()
                lines = []
                for tool in tools:
                    lines.append(f"- {tool.name}: {tool.description or '(no description)'}")
                    if tool.inputSchema and tool.inputSchema.get("properties"):
                        for param, schema in tool.inputSchema["properties"].items():
                            desc = schema.get("description", "")
                            lines.append(f"    {param}: {desc}")
                return "\n".join(lines) if lines else "No tools available."
        except Exception as exc:
            logger.error("Failed to fetch tools from MCP server: %s", exc)
            return "No tools available (MCP server unreachable)."

    async def _fetch_tool_names(self) -> List[str]:
        """Returns just the list of valid tool names for existence check."""
        try:
            async with Client(self._transport) as client:
                tools = await client.list_tools()
                return [t.name for t in tools]
        except Exception:
            return []

    async def _call_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Calls a tool on the MCP server.
        Returns the result dict on success.
        Returns {"ok": False, "error": "..."} on failure instead of raising,
        so the agent can format a clean error message for the user.
        """
        try:
            async with Client(self._transport) as client:
                result = await client.call_tool(
                    tool_name,
                    tool_args,
                    raise_on_error=False,   # we handle errors ourselves
                )
                # FastMCP returns result.data for successful calls
                return result.data if hasattr(result, "data") else result
        except ToolError as exc:
            logger.warning("MCP ToolError calling %s: %s", tool_name, exc)
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            logger.error("Unexpected error calling %s: %s", tool_name, exc)
            return {"ok": False, "error": f"Tool call failed: {exc}"}

    # ── LLM helpers ──────────────────────────────────────────────────────────

    async def _decide(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        tools_description: str,
    ) -> Dict[str, Any]:
        """
        Asks the LLM to pick a tool and extract its arguments.
        Returns a safe dict — never raises.
        """
        messages = [
            {
                "role": "system",
                "content": DECISION_PROMPT.format(tools=tools_description),
            },
            *history,
            {"role": "user", "content": user_message},
        ]
        raw = await self.llm.generate(messages)
        return self._parse_decision(raw)

    async def _respond(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        tool_result: Optional[Any],
    ) -> str:
        """Asks the LLM to format the final user-facing response."""
        if tool_result is not None:
            result_text = (
                json.dumps(tool_result, indent=2)
                if isinstance(tool_result, dict)
                else str(tool_result)
            )
            assistant_context = f"Tool result:\n{result_text}"
        else:
            assistant_context = "No tool was needed for this request."

        messages = [
            {"role": "system", "content": RESPONSE_PROMPT},
            *history,
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_context},
        ]
        return await self.llm.generate(messages)

    def _parse_decision(self, raw: str) -> Dict[str, Any]:
        """
        Safely parses the LLM's JSON decision.
        Strips markdown fences if present.
        Returns {"tool": "none", "args": {}} as safe fallback — never raises.
        """
        fallback = {"tool": "none", "args": {}, "reason": "parse failed"}
        try:
            clean = raw.strip()
            # Strip ```json ... ``` fences the LLM sometimes adds
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                )
            parsed = json.loads(clean.strip())
            if not isinstance(parsed, dict):
                return fallback
            # Ensure args is always a dict
            if not isinstance(parsed.get("args"), dict):
                parsed["args"] = {}
            return parsed
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned invalid JSON for tool decision: %s | raw: %.200s", exc, raw)
            return fallback