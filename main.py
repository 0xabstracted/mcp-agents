# main.py
import asyncio
import sys
from orchestrator import Orchestrator
from config import AGENT_SERVER_PARAMS # Import the configuration

async def main_loop():
    """Initializes the orchestrator and runs the interactive chat loop."""
    print("Starting MCP Orchestrator...")
    orchestrator = Orchestrator(AGENT_SERVER_PARAMS)
    initialized = False
    try:
        await orchestrator.initialize_agents()
        initialized = True
        print("\nOrchestrator Ready! Type your request or 'quit' to exit.")

        while True:
            try:
                user_input = input("\nYou: ").strip()
                if user_input.lower() == 'quit':
                    break
                if not user_input:
                    continue

                response = await orchestrator.handle_user_request(user_input)
                print(f"\nOrchestrator: {response}")

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\nAn unexpected error occurred in the chat loop: {e}")
                # Decide if you want to break or continue
                # break

    except Exception as e:
         print(f"\nFATAL ERROR during initialization: {e}")
    finally:
        if initialized: # Only cleanup if initialization was attempted/successful
             await orchestrator.cleanup()
        print("MCP Orchestrator stopped.")

if __name__ == "__main__":
    # Handle potential asyncio errors on Windows depending on Python version
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
         print("\nInterrupted by user.")