# mcp_client_wrapper.py
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

class MCPClientWrapper:
    """Handles connection and tool calls for a single MCP server process."""

    def __init__(self, server_params: StdioServerParameters):
        self.server_params = server_params
        self.session: Optional[ClientSession] = None
        self.available_tools: List[Tool] = []
        self._exit_stack = AsyncExitStack()
        self._stdio_reader = None
        self._stdio_writer = None
        self._transport_context = None
        self._session_context = None
        self.server_id = server_params.args[0] if server_params.args else "unknown_server"


    async def connect(self) -> List[Tool]:
        """Establishes connection to the MCP server and returns available tools."""
        print(f"Connecting to MCP server: {self.server_id}...")
        try:
            # Enter the stdio_client context
            self._transport_context = stdio_client(self.server_params)
            stdio_transport = await self._exit_stack.enter_async_context(self._transport_context)
            self._stdio_reader, self._stdio_writer = stdio_transport

            # Enter the ClientSession context
            self._session_context = ClientSession(self._stdio_reader, self._stdio_writer)
            self.session = await self._exit_stack.enter_async_context(self._session_context)

            await self.session.initialize()

            response = await self.session.list_tools()
            self.available_tools = response.tools or []
            tool_names = [tool.name for tool in self.available_tools]
            print(f"Connected to {self.server_id} with tools: {tool_names}")
            return self.available_tools
        except Exception as e:
            print(f"ERROR: Failed to connect or initialize session with {self.server_id}: {e}")
            await self.cleanup() # Attempt cleanup if connection failed
            self.available_tools = []
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Executes a tool call on the connected server."""
        if not self.session:
            raise ConnectionError(f"Session not established for {self.server_id}. Cannot call tool.")

        print(f"Calling tool '{tool_name}' on {self.server_id} with args: {arguments}")
        try:
            result = await self.session.call_tool(tool_name, arguments)
            print(f"Tool '{tool_name}' result from {self.server_id}: {result.content}")
            return result
        except Exception as e:
            print(f"ERROR: Failed to call tool '{tool_name}' on {self.server_id}: {e}")
            # Decide how to handle tool call errors - re-raise or return error result?
            # Returning a custom error structure might be useful for the orchestrator
            raise # Re-raising for now

    def get_tools(self) -> List[Tool]:
        """Returns the list of tools discovered on this connection."""
        return self.available_tools

    async def cleanup(self):
        """Closes the connection and cleans up resources."""
        print(f"Cleaning up connection to {self.server_id}...")
        await self._exit_stack.aclose()
        self.session = None
        self.available_tools = []
        print(f"Connection to {self.server_id} cleaned up.")