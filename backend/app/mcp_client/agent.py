import json
import os
import logging
import sys
import time
from typing import Any, Dict, List, Optional, Callable

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
Filtering rules
- Only include filters explicitly mentioned by the user.
- Do NOT invent filters such as payment_state, date ranges, or status.

Invoice filtering rules
- Only include payment_state if the user explicitly asks for payment status.
- Examples: unpaid, paid, partially paid, overdue.
- If the user only asks for invoices or posted invoices, do NOT include payment_state.

Counting rules
- count_only must be False by default.
- Use count_only=True ONLY when the user asks:
  "how many", "count", "number of", or "total".

Listing rules
- If the user says "show", "list", "display", or "get", count_only must be False.
- Listing requests should return invoice records.
STRICT ARGUMENT RULES:
- NEVER wrap scalar values inside objects.

Examples:
CORRECT: "move_type": "out_invoice"
WRONG: "move_type": {{"type": "out_invoice"}}

CORRECT: "payment_state": "not_paid"
WRONG: "payment_state": "unpaid"

- Follow parameter names and types EXACTLY as defined by the tool schema.
- Never invent parameter names.
- If a parameter is string, return string only.
- If a parameter is boolean, return boolean only.
- Never invent nested structures.

Invoice mapping rules:
- customer invoices -> move_type="out_invoice"
- vendor bills -> move_type="in_invoice"

Payment state mapping:
- unpaid -> "not_paid"
- partially paid -> "partial"
- paid -> "paid"
- overdue -> "overdue"
"""
DECISION_PROMPT += """

No-tool rules (return "tool": "none" for these):
- The user asks to summarize, analyze, or explain previous results.
- The user asks for predictions or trends based on data already in the conversation.
- The user says "don't use a tool", "just answer", or similar.
- The user asks a follow-up question about data that was already fetched.
- The user asks general ERP knowledge questions that do not require live data.
- The user is chatting, greeting, or asking who you are.
"""
# Few-shot examples to reduce Pydantic/schema errors. Keep double-brace escaping
# because this string is later formatted with DECISION_PROMPT.format(tools=...).
DECISION_PROMPT += """

Few-shot examples (must be valid JSON, follow parameter names exactly):

Example 1 — Count unpaid customer invoices in a date range:
{{
    "tool": "search_invoices_advanced",
    "args": {{
        "move_type": "out_invoice",
        "payment_state": "not_paid",
        "date_from": "2026-01-01",
        "date_to": "2026-05-31",
        "count_only": true
    }},
    "reason": "Count unpaid customer invoices from Jan to May 2026"
}}

Example 2 — List 20 unpaid invoices for a partner:
{{
    "tool": "search_invoices_advanced",
    "args": {{
        "move_type": "out_invoice",
        "payment_state": "not_paid",
        "partner_name": "ACME SARL",
        "limit": 20,
        "count_only": false
    }},
    "reason": "List 20 unpaid customer invoices for partner ACME"
}}

Example 3 — Create invoice: `invoice_payload` must be a JSON string (not an object):
{{
    "tool": "create_invoice",
    "args": {{
        "invoice_payload": "{{\"move_type\":\"out_invoice\",\"partner_id\":42,\"lines\":[{{\"description\":\"Consulting\",\"quantity\":1,\"unit_price\":500}}]}}"
    }},
    "reason": "Create invoice from canonical payload"
}}

Example 4 — Revenue from May 2025 until January 2025:
{{
    "tool": "get_revenue",
    "args": {{
        "year": 2025,
        "month": 5,
        "months_back": 5
    }},
    "reason": "Get the revenue range from January 2025 through May 2025, anchored at May 2025"
}}

Important rules reinforced:
- Follow tool parameter names exactly (move_type, payment_state, date_from, date_to, count_only).
- NEVER wrap scalar values inside objects (WRONG: "move_type": {{"type":"out_invoice"}}).
- Use the mapping: customer -> move_type="out_invoice", vendor -> move_type="in_invoice".
- Use payment_state values: unpaid -> "not_paid", partially paid -> "partial", paid -> "paid", overdue -> "overdue".
- For revenue range requests like "from May 2025 until January 2025", normalize to the end month as the anchor and set months_back to cover the span.
"""

RESPONSE_PROMPT = """You are a professional ERP assistant.

Given the user's message, the conversation history, and the tool result below (if any),
write a clear, helpful response.

Rules:
- If a tool result is provided, base your answer primarily on that result.
- If no tool result is provided, use the conversation history to answer.
  Look at previous assistant messages for data, numbers, or results.
- Do not claim success unless tool_result.ok is true.
- Do not expose internal IDs or raw JSON unless the user specifically asked.
- For summaries or predictions, reason explicitly from the numbers in the history.

Formatting rules:
- If the user asks for a table, return a clean markdown table.
- If multiple records are returned, present them as a readable list.
- Keep the output concise and aligned with the user's requested structure.
"""


class Agent:
    TOOLS_CACHE_TTL = 60.0  # seconds
    
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
        _mcp_env = dotenv_values(os.path.join(mcp_server_path, ".env"))

        logger.info("MCP server path: %s", mcp_server_path)
        logger.info("main.py exists: %s", os.path.exists(os.path.join(mcp_server_path, "main.py")))

        subprocess_env = {**os.environ}
        subprocess_env["ODOO_URL"] = _env.get("ODOO_URL") or _mcp_env.get("ODOO_URL", "")
        subprocess_env["ODOO_DB"] = _env.get("ODOO_DB") or _mcp_env.get("ODOO_DB", "")
        subprocess_env["ODOO_API_KEY"] = _env.get("ODOO_API_KEY") or _mcp_env.get("ODOO_API_KEY", "")
        subprocess_env["PYTHONPATH"]  = mcp_server_path
        subprocess_env["PYTHONIOENCODING"] = "utf-8"
        subprocess_env["PYTHONUTF8"]  = "1"
        
        self._mcp_server_path = mcp_server_path
        self._transport_kwargs = {
            "command": sys.executable,
            "args": ["main.py"],
            "cwd": mcp_server_path,
            "env": subprocess_env,
            "keep_alive": True,  # FastMCP handles concurrency via reference counting
        }
        
        # Initialize transport and client
        self._transport = StdioTransport(**self._transport_kwargs)
        self._client = Client(self._transport)
        
        # Tool cache with TTL
        self._tools_cache: Optional[List] = None
        self._tools_cache_ts: float = 0.0
    # ── Public entry point ───────────────────────────────────────────────────

    async def run(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        enforce_tool_only: bool = False,
    ) -> str:
        response, _ = await self.run_with_trace(
            user_message=user_message,
            history=history,
            enforce_tool_only=enforce_tool_only,
        )
        return response

    async def run_with_trace(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        enforce_tool_only: bool = False,
    ) -> tuple[str, Dict[str, Any]]:
        history = history or []
        trace: Dict[str, Any] = {
            "tool_called": False,
            "selected_tool": None,
            "tool_args": {},
            "tool_result": None,
            "reason": None,
            "progress": [],
            "tools_used": [],
        }
        trace["progress"].append("start")

        # Step 1 — fetch real tool list from MCP server
        tools_description = await self._fetch_tools_description()
        trace["progress"].append("fetched_tools_description")
        mcp_unreachable = "MCP server unreachable" in tools_description
        if mcp_unreachable:
            trace["progress"].append("mcp_unreachable")
            trace["known_tools"] = []
            if enforce_tool_only:
                response = "MCP server is currently unavailable. Please retry in a moment."
            else:
                response = await self._respond(user_message, history, tool_result=None)
            trace["progress"].append("done")
            return response, trace
        # Shortcut: if user asks for available tools, answer from MCP list directly.
        if self._is_tool_inventory_request(user_message):
            trace["progress"].append("inventory_request_detected")
            names = await self._fetch_tool_names()
            trace["selected_tool"] = "list_tools"
            trace["tool_called"] = True
            trace["tools_used"] = ["list_tools"]
            trace["known_tools"] = names
            trace["tool_result"] = {"ok": True, "tools": names}
            trace["progress"].append("listed_tools")
            if names:
                response = "Available MCP tools: " + ", ".join(names)
            else:
                response = "I could not fetch tools from MCP right now."
            trace["progress"].append("done")
            return response, trace
          # Shortcut: analysis/summarization of prior conversation data — skip tool decision
        if self._is_analysis_request(user_message):
            trace["progress"].append("analysis_request_detected")
            trace["selected_tool"] = "none"
            trace["reason"] = "User asked for analysis/summary — using conversation history"
            response = await self._respond(user_message, history, tool_result=None)
            trace["progress"].append("done")
            return response, trace

        # Step 2 — ask LLM to decide tool + arguments
        decision = await self._decide(user_message, history, tools_description)
        trace["progress"].append("tool_decision_complete")
        tool_name = decision.get("tool")
        tool_args = decision.get("args", {})
        trace["selected_tool"] = tool_name
        trace["tool_args"] = tool_args
        trace["reason"] = decision.get("reason")

        logger.info("Tool decision: tool=%s reason=%s", tool_name, decision.get("reason"))

        # Step 3 — handle "no tool" case
        if not tool_name or tool_name == "none":
            trace["progress"].append("no_tool_selected")
            known_tools = await self._fetch_tool_names()
            trace["known_tools"] = known_tools
            if enforce_tool_only:
                response = (
                    "I can only answer using MCP tools. "
                    f"No matching tool was selected for this request. Available tools: {', '.join(known_tools) or 'none'}."
                )
            else:
                response = await self._respond(user_message, history, tool_result=None)
            trace["progress"].append("done")
            return response, trace

        # Step 4 — check the tool actually exists on the MCP server
        known_tools = await self._fetch_tool_names()
        trace["progress"].append("fetched_tool_names")
        trace["known_tools"] = known_tools
        if not known_tools:
            trace["progress"].append("no_known_tools")
            response = "MCP server is currently unavailable. Please retry in a moment."
            trace["progress"].append("done")
            return response, trace
        if tool_name not in known_tools:
            logger.warning("LLM chose unknown tool: %s", tool_name)
            trace["progress"].append("selected_tool_not_found")
            response = (
                f"I couldn't find a tool called '{tool_name}'. "
                f"Available tools are: {', '.join(known_tools)}. "
                f"Please rephrase your request."
            )
            trace["progress"].append("done")
            return response, trace

        # Step 5 — call the tool on the MCP server
        trace["progress"].append("calling_tool")
        tool_result = await self._call_tool(tool_name, tool_args)
        trace["tool_called"] = True
        trace["tools_used"] = [tool_name]
        trace["tool_result"] = tool_result
        trace["progress"].append("tool_call_finished")

        # Step 6 — format final response
        response = await self._respond(user_message, history, tool_result)
        trace["progress"].append("response_formatted")
        trace["progress"].append("done")
        return response, trace

    def _is_tool_inventory_request(self, user_message: str) -> bool:
        text = (user_message or "").strip().lower()
        patterns = (
            "what tools",
            "which tools",
            "list tools",
            "available tools",
            "tool list",
            "what mcp tools",
            "what can you do with tools",
        )
        return any(p in text for p in patterns)

    def _is_analysis_request(self, user_message: str) -> bool:
        """Detect requests that want analysis/summary/prediction on prior data — no tool needed."""
        text = (user_message or "").strip().lower()
        patterns = (
            "summarize", "summary", "summarise",
            "predict", "prediction", "forecast",
            "based on the data", "based on these results", "based on what you found",
            "from the results", "from the data above", "from the above",
            "analyze that", "analyse that", "analyze the results", "analyse the results",
            "what does this mean", "what does that mean",
            "give me insights", "any insights",
            "don't use a tool", "without a tool", "no tool",
            "just answer", "answer directly",
            "explain the results", "explain these numbers",
            "what trends", "any trends","table"
        )
        return any(p in text for p in patterns)
    # ── MCP reconnect and caching ────────────────────────────────────────────

    async def _mcp_call(self, operation: Callable) -> Any:
        """
        Executes an MCP operation with one automatic reconnect on failure.
        This handles the case where the subprocess died unexpectedly.
        FastMCP Client handles concurrent async with blocks via reference counting.
        """
        for attempt in range(2):
            try:
                async with self._client as client:
                    return await operation(client)
            except Exception as exc:
                if attempt == 0:
                    logger.warning(
                        "MCP call failed (attempt 1), rebuilding client: %s", exc
                    )
                    # Rebuild client — spawns a fresh subprocess on next async with
                    self._transport = StdioTransport(**self._transport_kwargs)
                    self._client = Client(self._transport)
                    self._tools_cache = None  # invalidate cache on reconnect
                    continue
                # Second attempt failed, will raise on exit
                raise

    async def _get_tools(self, client) -> List:
        """Fetch tools from MCP server, using cache if fresh."""
        now = time.monotonic()
        if self._tools_cache and (now - self._tools_cache_ts) < self.TOOLS_CACHE_TTL:
            logger.debug("Returning cached tool list (age: %.1fs)", now - self._tools_cache_ts)
            return self._tools_cache
        
        tools = await client.list_tools()
        self._tools_cache = tools
        self._tools_cache_ts = now
        logger.debug("Fetched and cached %d tools from MCP server", len(tools))
        return tools

    # ── MCP client helpers ───────────────────────────────────────────────────

    async def _fetch_tools_description(self) -> str:
        """
        Fetches tool descriptions from MCP server for LLM system prompt.
        Uses cached tool list if available (TTL: 60s).
        """
        try:
            async def op(client):
                tools = await self._get_tools(client)
                lines = []
                for tool in tools:
                    lines.append(f"- {tool.name}: {tool.description or '(no description)'}")
                    if tool.inputSchema and tool.inputSchema.get("properties"):
                        for param, schema in tool.inputSchema["properties"].items():
                            desc = schema.get("description", "")
                            lines.append(f"    {param}: {desc}")
                return "\n".join(lines) if lines else "No tools available."

            return await self._mcp_call(op)
        except Exception as exc:
            logger.error("Failed to fetch tools from MCP server: %s", exc)
            return "No tools available (MCP server unreachable)."

    async def _fetch_tool_names(self) -> List[str]:
        """Returns just the list of valid tool names for existence check."""
        try:
            async def op(client):
                tools = await self._get_tools(client)
                return [t.name for t in tools]

            return await self._mcp_call(op)
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
        Returns {"ok": False, "error": "..."} on failure instead of raising.
        """
        # Ensure invoice_payload is a JSON string
        if tool_name == "create_invoice":
            payload = tool_args.get("invoice_payload")
            if payload is None and tool_args:
                payload = tool_args
            if isinstance(payload, dict):
                tool_args = {
                    "invoice_payload": json.dumps(payload, ensure_ascii=False),
                }

        try:
            async def op(client):
                result = await client.call_tool(
                    tool_name,
                    tool_args,
                    raise_on_error=False,
                )
                return result

            result = await self._mcp_call(op)

            # FastMCP 3.x can return payload in `data` or `content`.
            if hasattr(result, "data") and result.data is not None:
                return result.data

            if hasattr(result, "content") and result.content:
                texts = [
                    getattr(item, "text", None)
                    for item in result.content
                    if getattr(item, "text", None)
                ]
                if texts:
                    joined = "\n".join(texts)
                    try:
                        return json.loads(joined)
                    except Exception:
                        return {
                            "ok": not bool(getattr(result, "is_error", False)),
                            "content": joined,
                        }

            return {"ok": not bool(getattr(result, "is_error", False)), "raw": str(result)}

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
        raw = await self.llm.generate(messages, temperature=0.1)
        return self._parse_decision(raw)

    async def _respond(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        tool_result: Optional[Any],
    ) -> str:
        """Asks the LLM to format the final user-facing response."""
        if isinstance(tool_result, dict) and tool_result.get("ok") is True:
            direct_response = tool_result.get("response")
            if isinstance(direct_response, str) and direct_response.strip():
                return direct_response.strip()

        fallback = self._format_tool_result_fallback(tool_result)
        if tool_result is not None:
            result_text = (
                json.dumps(tool_result, indent=2)
                if isinstance(tool_result, dict)
                else str(tool_result)
            )
            assistant_context = f"Tool result:\n{result_text}"
        else:
            assistant_context = "No tool was called for this request. Use the conversation history above to answer the user directly.If previous messages contain data, numbers, or results, use that information to summarize, analyze, or predict as requested. "

        messages = [
            {"role": "system", "content": RESPONSE_PROMPT},
            *history,
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_context},
        ]
        try:
            text = await self.llm.generate(messages, temperature=0.8)
            if text and text.strip():
                return text
            return fallback
        except Exception as exc:
            logger.warning("LLM response formatting failed, using fallback: %s", exc)
            return fallback

    def _format_tool_result_fallback(self, tool_result: Optional[Any]) -> str:
        """Deterministic response when LLM formatter fails or returns blank."""
        if tool_result is None:
            return "No tool result was available."

        if isinstance(tool_result, dict):
            ok = tool_result.get("ok")
            if ok is True:
                if "message" in tool_result and tool_result["message"]:
                    return str(tool_result["message"])
                if "invoice" in tool_result and isinstance(tool_result["invoice"], dict):
                    invoice_id = tool_result["invoice"].get("id")
                    return f"Tool executed successfully. Invoice id: {invoice_id}."
                return "Tool executed successfully."

            if ok is False:
                err = tool_result.get("error") or tool_result.get("content") or "Unknown tool error."
                return f"Tool execution failed: {err}"

            return f"Tool execution result: {json.dumps(tool_result, ensure_ascii=True)}"

        return f"Tool execution result: {str(tool_result)}"

    def _parse_decision(self, raw: str) -> Dict[str, Any]:
        """
        Safely parses the LLM's JSON decision.
        Strips markdown fences if present.
        Converts invoice_payload dict to JSON string if needed.
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
            clean = clean.strip()
            decoder = json.JSONDecoder()
            start = clean.find("{")
            if start == -1:
                return fallback

            parsed, _ = decoder.raw_decode(clean[start:])
            if not isinstance(parsed, dict):
                return fallback
            
            # Ensure args is always a dict
            if not isinstance(parsed.get("args"), dict):
                parsed["args"] = {}
            
            # Fix invoice_payload if LLM returned a dict instead of JSON string
            args = parsed.get("args", {})
            if isinstance(args.get("invoice_payload"), dict):
                args["invoice_payload"] = json.dumps(
                    args["invoice_payload"], ensure_ascii=False
                )
                parsed["args"] = args
            
            return parsed
        except json.JSONDecodeError as exc:
            logger.debug("LLM returned non-parseable tool decision, falling back: %s", exc)
            return fallback