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
"""

RESPONSE_PROMPT = """You are a professional ERP assistant. 
Given the user's message and the tool result below, write a clear, 
helpful response based ONLY on the tool result. Be concise.

Rules:
- Do not use outside knowledge.
- If tool result indicates failure, explain the failure and what input is needed.
- Do not claim success unless tool_result.ok is true.
- Do not expose internal IDs or raw JSON unless the user specifically asked for them.
- If multiple records are returned, present them as a readable list.
Formatting rules:
- If the tool returns multiple records, list them clearly.
- Do NOT summarize results when records are available.
- For invoices, show important fields such as invoice number, partner, amount, and due date.
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
        enforce_tool_only: bool = True,
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
        enforce_tool_only: bool = True,
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
        raw = await self.llm.generate(messages)
        return self._parse_decision(raw)

    async def _respond(
        self,
        user_message: str,
        history: List[Dict[str, str]],
        tool_result: Optional[Any],
    ) -> str:
        """Asks the LLM to format the final user-facing response."""
        # Deterministic formatting for read-style results to avoid generic responses.
        if isinstance(tool_result, dict) and tool_result.get("ok") is True:
            direct_response = tool_result.get("response")
            if isinstance(direct_response, str) and direct_response.strip():
                return direct_response.strip()

            summary = tool_result.get("summary")
            if isinstance(summary, dict) and summary:
                message = str(tool_result.get("message") or "").lower()

                if "invoice" in message or any(
                    key in summary for key in ("state", "amount_total", "partner")
                ):
                    header = str(tool_result.get("message") or "Invoice details")
                    lines = [header, ""]
                    if summary.get("id") is not None:
                        lines.append(f"ID: {summary.get('id')}")
                    if summary.get("name"):
                        lines.append(f"Number: {summary.get('name')}")
                    if summary.get("state"):
                        lines.append(f"State: {summary.get('state')}")
                    if summary.get("partner"):
                        lines.append(f"Partner: {summary.get('partner')}")
                    if summary.get("amount_total") is not None:
                        lines.append(f"Total: {summary.get('amount_total')}")
                    return "\n".join(lines)

                if "partner" in message or any(
                    key in summary for key in ("customer_rank", "supplier_rank", "is_company")
                ):
                    is_creation = "create" in message or "created" in message or "new contact" in message
                    header = "Partner created successfully" if is_creation else "Partner data fetched successfully"
                    lines = [header, ""]
                    if summary.get("id") is not None:
                        lines.append(f"ID: {summary.get('id')}")
                    if summary.get("name"):
                        lines.append(f"Name: {summary.get('name')}")
                    if summary.get("email"):
                        lines.append(f"Email: {summary.get('email')}")
                    if summary.get("phone"):
                        lines.append(f"Phone: {summary.get('phone')}")
                    if summary.get("is_company") is not None:
                        lines.append(f"Is Company: {summary.get('is_company')}")
                    if summary.get("customer_rank") is not None:
                        lines.append(f"Customer Rank: {summary.get('customer_rank')}")
                    if summary.get("supplier_rank") is not None:
                        lines.append(f"Supplier Rank: {summary.get('supplier_rank')}")
                    return "\n".join(lines)

        fallback = self._format_tool_result_fallback(tool_result)
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
        try:
            text = await self.llm.generate(messages)
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
            parsed = json.loads(clean.strip())
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
            logger.warning("LLM returned invalid JSON for tool decision: %s | raw: %.200s", exc, raw)
            return fallback