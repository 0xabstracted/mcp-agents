# agent_wrapper.py
import asyncio
from typing import List, Dict, Any

from mcp import StdioServerParameters, Tool
from mcp.types import CallToolResult # <-- Correct import
from mcp_client_wrapper import MCPClientWrapper

class AgentWrapper:
    """Manages MCPClientWrappers for a specific agent role."""

    def __init__(self, agent_name: str, server_params_list: List[StdioServerParameters]):
        self.agent_name = agent_name
        self.server_params_list = server_params_list
        self.clients: Dict[str, MCPClientWrapper] = {} # Key: server_id (path), Value: client wrapper
        self.available_tools: List[Tool] = []
        self.tool_to_client_map: Dict[str, MCPClientWrapper] = {} # Key: tool_name, Value: client wrapper

    async def connect_all(self):
        """Connects all associated MCP clients."""
        print(f"Initializing connections for {self.agent_name}...")
        connection_tasks = []
        temp_clients = {}

        for params in self.server_params_list:
            client = MCPClientWrapper(params)
            server_id = client.server_id
            temp_clients[server_id] = client
            connection_tasks.append(client.connect()) # Connect returns the list of tools

        # Run connections concurrently
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)

        # Process results and populate maps
        self.clients = {} # Reset in case of reconnection
        self.available_tools = []
        self.tool_to_client_map = {}

        for i, result in enumerate(results):
            params = self.server_params_list[i]
            server_id = params.args[0] if params.args else f"unknown_{i}"
            client = temp_clients.get(server_id) # Get the client instance

            if isinstance(result, Exception):
                print(f"ERROR: Failed to connect client for {self.agent_name} to {server_id}: {result}")
                # Optionally try to clean up the failed client instance if needed
                if client:
                    await client.cleanup()
            elif isinstance(result, list): # Expected result is list of Tools
                 if client:
                    self.clients[server_id] = client
                    tools = result
                    self.available_tools.extend(tools)
                    for tool in tools:
                        if tool.name in self.tool_to_client_map:
                            print(f"WARNING: Duplicate tool name '{tool.name}' found. Agent: {self.agent_name}. Using connection to {server_id}.")
                        self.tool_to_client_map[tool.name] = client # Maps tool name to the client instance
            else:
                 print(f"Warning: Unexpected connection result for {server_id}: {result}")
                 if client: # Still cleanup if unexpected result
                    await client.cleanup()

        print(f"{self.agent_name} initialized. Total tools available: {len(self.available_tools)}")
        if not self.clients:
             print(f"WARNING: {self.agent_name} failed to connect to any servers.")


    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> CallToolResult:
        """Finds the correct client and executes the tool."""
        client = self.tool_to_client_map.get(tool_name)
        if not client:
            raise ValueError(f"Tool '{tool_name}' not found or client not available for agent '{self.agent_name}'.")

        return await client.call_tool(tool_name, tool_args)

    def get_tools(self) -> List[Tool]:
        """Returns all tools available to this agent."""
        return self.available_tools

    def get_tools_for_llm(self) -> List[Dict[str, Any]]:
         """Formats tools for the Anthropic API 'tools' parameter."""
         return [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
         } for tool in self.available_tools]


    async def cleanup(self):
        """Cleans up all managed client connections."""
        print(f"Cleaning up clients for {self.agent_name}...")
        cleanup_tasks = [client.cleanup() for client in self.clients.values()]
        await asyncio.gather(*cleanup_tasks, return_exceptions=True) # Handle potential cleanup errors
        print(f"Clients for {self.agent_name} cleaned up.")