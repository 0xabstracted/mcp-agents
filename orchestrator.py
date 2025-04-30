# orchestrator.py with specialized agent prompts
import asyncio
import os
import json
from typing import Dict, List, Any
import re

from anthropic import Anthropic, AsyncAnthropic
from dotenv import load_dotenv

from agent_wrapper import AgentWrapper # Import our agent wrapper
from mcp import Tool # For type hinting
from config import FILESYSTEM_ALLOWED_DIRS, GIT_REPOSITORY_PATH, KNOWN_EMAILS

# Load API key from .env
load_dotenv()

def resolve_email_address(recipient: str, known_emails: dict) -> str:
    """
    Resolves a recipient string to a valid email address using known_emails.
    Handles aliases, malformed addresses like 'chris@kris_fagerlie@hotmail.com', and direct emails.
    """
    recipient = recipient.lower().strip()
    # Direct alias
    if recipient in known_emails:
        return known_emails[recipient]
    # Malformed: alias@real_email
    match = re.match(r"^([a-z0-9._-]+)@([a-z0-9._-]+@[a-z0-9._-]+\.[a-z]+)$", recipient)
    if match:
        alias = match.group(1)
        if alias in known_emails:
            return known_emails[alias]
        # If not, fallback to the right side
        return match.group(2)
    # Looks like a valid email
    if "@" in recipient and "." in recipient.split("@")[-1]:
        return recipient
    # Fallback: return as-is or raise
    return recipient

class Orchestrator:
    """Manages agents, plans tasks, and interacts with the user."""

    def __init__(self, agent_server_params: Dict[str, List[Any]]):
        self.anthropic = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        if not self.anthropic.api_key:
             raise ValueError("ANTHROPIC_API_KEY not found in environment variables.")

        self.agents: Dict[str, AgentWrapper] = {}
        self.agent_server_params = agent_server_params
        self.all_tools_for_planning: List[Dict[str, Any]] = [] # Formatted for LLM planning

    async def initialize_agents(self):
        """Creates and connects all agents defined in the config."""
        print("Initializing orchestrator agents...")
        initialization_tasks = []
        agent_names = list(self.agent_server_params.keys())

        for agent_name in agent_names:
            params = self.agent_server_params[agent_name]
            agent = AgentWrapper(agent_name, params)
            self.agents[agent_name] = agent
            initialization_tasks.append(agent.connect_all())

        await asyncio.gather(*initialization_tasks) # Connect all agents concurrently

        # Aggregate tools for planning after all agents are connected
        self._aggregate_tools_for_planning()
        print("Orchestrator agents initialized.")

    def _aggregate_tools_for_planning(self):
        """Formats all available tools from all agents for the planning LLM call."""
        self.all_tools_for_planning = []
        for agent_name, agent in self.agents.items():
            agent_tools = agent.get_tools()
            for tool in agent_tools:
                 # Add agent context to the description for the planner LLM
                self.all_tools_for_planning.append({
                    "name": tool.name,
                    "description": f"Agent '{agent_name}' can use this tool. Description: {tool.description}",
                    "input_schema": tool.inputSchema
                })
        # print(f"Aggregated tools for planning: {json.dumps(self.all_tools_for_planning, indent=2)}")


    async def _get_plan_from_llm(self, user_query: str) -> List[Dict[str, str]]:
        """Asks the LLM to create a step-by-step plan."""
        agent_descriptions = "\n".join([
            "- SearchAgent: Manages web search tools through Brave Search API for finding information online.",
            "- ComsAgent: Handles email communications, filesystem operations, and maintains a knowledge graph memory. Can send emails, manage files, and store/retrieve information about users and entities.",
            "- GitAgent: Manages GitHub repository operations including creating repositories, pushing files, and managing commits."
        ])

        # NEW: Add known emails to the prompt
        known_emails_str = "\n".join([f"  - {alias} → {email}" for alias, email in KNOWN_EMAILS.items()])
        known_emails_section = f"""
KNOWN EMAILS (for use in ComsAgent tasks):
{known_emails_str}

When planning any step that involves sending an email, always use the correct email address from this list if the recipient is mentioned by name or alias.
"""

        system_prompt = f"""You are an orchestrator managing three specialist agents:
{agent_descriptions}
{known_emails_section}
Your task is to break down the user's request into a sequence of steps. Each step should specify the 'agent' responsible and the 'task' for that agent.

IMPORTANT: When a step depends on information from a previous step, explicitly include this in the task description by using step_X_result placeholder. For example: "Use send_email to send the price information from {{step_1_result}} to the customer".

IMPORTANT: For filesystem operations, always use SPECIFIC file paths rather than vague references. For most file operations, use `/Users/kristianfagerlie/apps/agentrepo/specialagent2/hello_world.md` as the default location.

IMPORTANT: For memory operations, use the ComsAgent's memory tools to store and retrieve information about users, entities, and their relationships. This includes:
- Creating entities (people, organizations, events)
- Adding observations about entities
- Creating relationships between entities
- Searching for information in the knowledge graph

Agent capabilities:
1. SearchAgent: Use for web searches to find information online
2. ComsAgent: Use for sending emails, managing files, and maintaining the knowledge graph memory
3. GitAgent: Use for GitHub repository operations

Use the tools available to the agents to decide the plan. Available tools (prefixed with the agent that provides them):
{json.dumps(self.all_tools_for_planning, indent=2)}

IMPORTANT: Your response MUST be a valid JSON array with no text before or after. Do not include any explanation, just the JSON array.

Respond ONLY with a JSON list of steps, like this:
[
  {{"agent": "AgentName1", "task": "Specific task for Agent 1 using its tools"}},
  {{"agent": "AgentName2", "task": "Specific task for Agent 2, potentially using results from step 1"}}
]
If the request cannot be fulfilled with the available agents and tools, respond with an empty JSON list: [].
"""
        print("\n--- Generating Plan ---")
        try:
            response = await self.anthropic.messages.create(
                model="claude-3-5-sonnet-20240620", # Or your preferred model
                max_tokens=1000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_query}]
            )
            plan_text = response.content[0].text.strip()
            print(f"LLM Plan Response:\n{plan_text}")
            
            # Try to extract JSON from the response by finding the first '[' and last ']'
            json_start = plan_text.find('[')
            json_end = plan_text.rfind(']') + 1
            
            if json_start != -1 and json_end > json_start:
                json_text = plan_text[json_start:json_end]
                plan = json.loads(json_text)
            else:
                plan = json.loads(plan_text)  # Try the original text as fallback
            
            if not isinstance(plan, list):
                 raise ValueError("LLM did not return a list for the plan.")
            # Basic validation
            for step in plan:
                if not isinstance(step, dict) or "agent" not in step or "task" not in step:
                    raise ValueError(f"Invalid step format in plan: {step}")
                if step["agent"] not in self.agents:
                     raise ValueError(f"Plan references unknown agent: {step['agent']}")
            return plan
        except (json.JSONDecodeError, ValueError, Exception) as e:
            print(f"ERROR: Failed to get or parse plan from LLM: {e}")
            print(f"LLM Raw Response was: {plan_text if 'plan_text' in locals() else 'Unavailable'}")
            return [] # Return empty plan on error

    async def _execute_agent_task(self, agent_name: str, task_description: str, context: Dict[str, Any]) -> str:
        """Handles the execution of a single task by the specified agent using its tools."""
        agent = self.agents.get(agent_name)
        if not agent:
            return f"Error: Agent '{agent_name}' not found."

        agent_tools = agent.get_tools_for_llm() # Get tools formatted for Claude call
        if not agent_tools:
             return f"Error: Agent '{agent_name}' has no tools available or failed to connect."

        # Prepare context information for the task
        context_info = ""
        for key, value in context.items():
            context_info += f"\n{key}: {value}"

        # Inject context into the task description (simple substitution)
        try:
            formatted_task = task_description.format(**context)
        except KeyError as e:
            print(f"Warning: Could not format task '{task_description}' with context {context}. Missing key: {e}")
            formatted_task = task_description # Use original task if formatting fails

        print(f"\n--- Executing Task for {agent_name} ---")
        print(f"Task: {formatted_task}")

        # Create specialized system prompts for each agent type
        if agent_name == "SearchAgent":
            system_prompt = f"""You are SearchAgent, specialized in finding information on the web using the Brave search API.
Your goal is to accomplish the following task: {formatted_task}. 
Always be thorough and comprehensive in your searches, and provide a clear summary of the search results.

Previous step results: {context_info}

When using information from previous steps, incorporate it directly into your actions rather than just referencing it."""

        elif agent_name == "ComsAgent":
            system_prompt = f"""You are ComsAgent, specialized in sending emails, managing files, and maintaining a knowledge graph memory.
Your goal is to accomplish the following task: {formatted_task}.

For email tasks:
- Format emails professionally with a clear subject line, greeting, body, and sign-off
- Include all relevant information from previous steps directly in the email body
- Use the correct email addresses from the known emails list

For memory tasks:
- Create entities for people, organizations, and significant events
- Add relevant observations about entities
- Create relationships between entities
- Search for information in the knowledge graph when needed
- Store new information in the knowledge graph for future reference

For file operations:
- Use specific file paths rather than vague references
- Be clear about file operations (read, write, create, delete)

Previous step results: {context_info}

When using information from previous steps, incorporate it directly into your actions rather than just referencing it."""

        elif agent_name == "GitAgent":
            system_prompt = f"""You are GitAgent, specialized in Git operations for the repository at {GIT_REPOSITORY_PATH}.
Your goal is to accomplish the following task: {formatted_task}.
You can perform Git operations like checking status, committing changes, creating branches, etc.
Always provide clear explanations of Git actions taken or Git information retrieved.

Previous step results: {context_info}

When using information from previous steps, incorporate it directly into your actions rather than just referencing it."""

        else:
            # Generic system prompt for any other agent
            system_prompt = f"""You are {agent_name}. Your goal is to accomplish the following task: {formatted_task}. Use your available tools if necessary.

Previous step results: {context_info}

When using information from previous steps, incorporate it directly into your actions rather than just referencing it."""

        # Also include context in the first user message to ensure it's available
        user_message = f"""Task: {formatted_task}

Previous step results: {context_info}"""

        messages = [{"role": "user", "content": user_message}] # Start with the enhanced task

        max_turns = 5 # Limit tool use cycles to prevent infinite loops
        turn_count = 0

        while turn_count < max_turns:
            turn_count += 1
            print(f"Agent '{agent_name}' - Turn {turn_count}")
            try:
                response = await self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20240620", # Use a capable model for tool use
                    max_tokens=1500,
                    system=system_prompt,
                    messages=messages,
                    tools=agent_tools
                )

                # Append assistant's response (thinking or final answer)
                assistant_response_content = []
                tool_calls_made = False

                for content_block in response.content:
                    if content_block.type == "text":
                        print(f"Agent '{agent_name}' Text Response: {content_block.text}")
                        assistant_response_content.append({"type": "text", "text": content_block.text})
                    elif content_block.type == "tool_use":
                        tool_calls_made = True
                        tool_name = content_block.name
                        tool_args = content_block.input
                        tool_use_id = content_block.id

                        # PATCH: If this is send_email, fix the 'to' field if needed
                        if tool_name == "send_email" and "to" in tool_args:
                            fixed_to = []
                            for recipient in tool_args["to"]:
                                fixed_to.append(resolve_email_address(recipient, KNOWN_EMAILS))
                            tool_args["to"] = fixed_to

                        print(f"Agent '{agent_name}' wants to use tool: {tool_name}({tool_args})")
                        assistant_response_content.append({"type": "tool_use", "id": tool_use_id, "name": tool_name, "input": tool_args})

                        # Execute the tool using the agent wrapper
                        try:
                            tool_result = await agent.execute_tool(tool_name, tool_args)
                            # Prepare message for next LLM turn
                            messages.append({"role": "assistant", "content": assistant_response_content})
                            messages.append({
                                "role": "user",
                                "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "content": tool_result.content # Assuming result.content is suitable (list of text/json blocks)
                                    # May need adjustment based on actual tool result structure
                                }]
                            })
                            print(f"Tool '{tool_name}' executed successfully.")
                        except Exception as tool_error:
                            print(f"ERROR executing tool '{tool_name}': {tool_error}")
                            # Inform the LLM the tool call failed
                            messages.append({"role": "assistant", "content": assistant_response_content})
                            messages.append({
                                "role": "user",
                                "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": tool_use_id,
                                    "is_error": True,
                                    "content": f"Error executing tool: {str(tool_error)}"
                                }]
                            })
                            # Allow LLM to potentially recover or report failure


                if not tool_calls_made:
                    # If no tool calls were made, this is the final text response for this task
                    final_text = " ".join([block.text for block in response.content if block.type == 'text'])
                    print(f"Agent '{agent_name}' finished task execution.")
                    return final_text # Task complete

            except Exception as e:
                print(f"ERROR during agent '{agent_name}' task execution turn {turn_count}: {e}")
                return f"Error during {agent_name} execution: {e}"

        # If loop finishes without returning, max turns were reached
        print(f"Warning: Agent '{agent_name}' reached max turns ({max_turns}). Returning last known state.")
        # Try to extract the last text response if available
        last_text = ""
        if messages and messages[-1]["role"] == "assistant":
             last_text = " ".join([block.get("text","") for block in messages[-1].get("content",[]) if block.get("type") == 'text'])
        return f"Max turns reached for {agent_name}. Last response: {last_text}" if last_text else f"Max turns reached for {agent_name}."

    async def handle_user_request(self, user_query: str) -> str:
        """Handles the full process from user query to final response."""
        print(f"\n=== Handling User Request: {user_query} ===")
        
        # 1. Get Plan
        plan = await self._get_plan_from_llm(user_query)
        if not plan:
            return "Sorry, I couldn't create a plan to fulfill your request with the available agents."
        
        # 2. Execute Plan
        step_results: Dict[str, Any] = {} # Store results from each step for context
        final_result = "Plan execution started..."

        for i, step in enumerate(plan):
            agent_name = step["agent"]
            task = step["task"]
            print(f"\nExecuting Step {i+1}/{len(plan)}: Agent='{agent_name}', Task='{task}'")

            # Execute the task, passing previous results as context
            step_output = await self._execute_agent_task(agent_name, task, step_results)

            # Store result using a generic key (e.g., step_1_result) or try to infer better key
            step_key = f"step_{i+1}_result" # Simple key based on step number
            step_results[step_key] = step_output
            print(f"Step {i+1} Result ({step_key}): {step_output}")
            final_result = step_output # Update final result to the latest step's output

            # Basic error check - stop if a step failed badly
            if "Error:" in step_output:
                 print(f"Stopping plan execution due to error in step {i+1}.")
                 return f"An error occurred during execution: {step_output}"

        print("=== Plan Execution Finished ===")
        # Return the result of the last step, or potentially synthesize a summary
        return final_result

    async def cleanup(self):
        """Cleans up all managed agent wrappers."""
        print("Cleaning up orchestrator agents...")
        cleanup_tasks = [agent.cleanup() for agent in self.agents.values()]
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        await self.anthropic.close() # Close the Anthropic client
        print("Orchestrator cleanup complete.")