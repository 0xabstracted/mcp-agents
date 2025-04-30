# config.py
import os
from mcp import StdioServerParameters
from dotenv import load_dotenv

# Load environment variables from .env file, including the GitHub token
load_dotenv()

# --- IMPORTANT: REPLACE THESE PATHS ---
# Use absolute paths for all server paths and directories

# Example paths - MODIFY THESE
SEARCH_SERVER_PATH = "./servers/brave-server/build/index.js"  # Path to the brave-search server
EMAIL_SERVER_PATH = "./servers/email-server/build/index.js"    # Path to the email server
GIT_REPOSITORY_PATH = "./repository"            # Path to the git repository
MEMORY_FILE_PATH = "./memory.json"  # Path to the memory file

# --- DIRECTORIES ALLOWED FOR FILESYSTEM SERVER ---
# Add one or more *absolute paths* to directories you want the FileSystemAgent to access.
# The server will be sandboxed to ONLY these directories and their subdirectories.
FILESYSTEM_ALLOWED_DIRS = [
    "./repository",  # Example - REPLACE or ADD your desired paths
]  # <<<--- CONFIGURE THESE PATHS!

# --- Get GitHub Token ---
GITHUB_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
# --- END OF PATHS TO REPLACE ---

# --- Path Checks ---
if not os.path.exists(SEARCH_SERVER_PATH):
    print(f"Warning: Search server path not found: {SEARCH_SERVER_PATH}")
if not os.path.exists(EMAIL_SERVER_PATH):
    print(f"Warning: Email server path not found: {EMAIL_SERVER_PATH}")
if not os.path.isdir(GIT_REPOSITORY_PATH):
    print(f"Warning: Git repository path not found or not a directory: {GIT_REPOSITORY_PATH}")
# Check filesystem directory paths
for dir_path in FILESYSTEM_ALLOWED_DIRS:
    if not os.path.isdir(dir_path):
        print(f"Warning: Filesystem allowed directory not found or not a directory: {dir_path}")
if not GITHUB_TOKEN:
    print("Warning: GITHUB_PERSONAL_ACCESS_TOKEN not set in environment. GitHubAgent will not be configured.")
# --- End Path Checks ---

AGENT_SERVER_PARAMS = {
    # Search Agent - Handles web searches
    "SearchAgent": [
        StdioServerParameters(command="node", args=[SEARCH_SERVER_PATH]),
    ],
    
    # Coms Agent - Handles communication (email), file operations, and memory
    "ComsAgent": [
        # Email server
        StdioServerParameters(command="node", args=[EMAIL_SERVER_PATH]),
        # Filesystem server
        StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-filesystem",
                *FILESYSTEM_ALLOWED_DIRS
            ]
        ),
        # Memory server
        StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-memory"
            ],
            env={
                "MEMORY_FILE_PATH": MEMORY_FILE_PATH
            }
        ),
    ],
    
    # Git Agent - Handles GitHub operations
    "GitAgent": [
        StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-github"
            ],
            env={
                "GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN
            }
        ),
    ]
}

# Known email aliases for planning
KNOWN_EMAILS = {
    "you": "you@example.com"
}
