# MCP Agents - AI Agent System

A powerful AI agent system built using the Model Context Protocol (MCP) framework, featuring specialized agents for search, communication, and GitHub operations. This is an example implementation demonstrating how to build custom AI agents using the MCP framework.

## About MCP

The Model Context Protocol (MCP) is an open protocol that enables seamless integration between LLM applications and external data sources and tools. Learn more at [modelcontextprotocol.io](https://modelcontextprotocol.io).

Official MCP servers and SDKs can be found at [github.com/modelcontextprotocol](https://github.com/modelcontextprotocol).

## System Architecture

The system consists of three specialized agents working together:

1. **SearchAgent**: Handles web searches using the Brave Search API
2. **ComsAgent**: Manages email communications, filesystem operations, and maintains a knowledge graph memory
3. **GitAgent**: Handles GitHub repository operations

## Prerequisites

- Python 3.8+
- Node.js and npm
- A GitHub Personal Access Token
- Anthropic API Key (for Claude AI)
- Brave Search API Key (optional, for enhanced search capabilities)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/0xabstracted/mcpagents.git
cd mcpagents
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install MCP servers:
```bash
# Install Memory Server
npx -y @modelcontextprotocol/server-memory

# Install Filesystem Server
npx -y @modelcontextprotocol/server-filesystem

# Install GitHub Server
npx -y @modelcontextprotocol/server-github
```

4. Create a `.env` file in the root directory with your API keys:
```env
ANTHROPIC_API_KEY=your_anthropic_api_key
GITHUB_PERSONAL_ACCESS_TOKEN=your_github_token
```

## Configuration

Edit `config.py` to set up your system paths and configurations:

1. Set up your local servers:
```python
# These paths point to your local server builds
SEARCH_SERVER_PATH = "/path/to/your/brave-server/build/index.js"
EMAIL_SERVER_PATH = "/path/to/your/email-server/build/index.js"
```

2. Configure the Git repository path:
```python
GIT_REPOSITORY_PATH = "/path/to/your/repository"
```

3. Set up allowed filesystem directories:
```python
FILESYSTEM_ALLOWED_DIRS = [
    "/path/to/allowed/directory",
]
```

4. Configure known email aliases:
```python
KNOWN_EMAILS = {
    "chris": "chris@example.com",
    "kris": "kris@example.com",
    "boss": "boss@example.com"
}
```

## Usage

1. Start the system:
```bash
python main.py
```

2. Interact with the system through the command-line interface. The system supports various commands:
- Web searches
- Email communications
- File operations
- GitHub repository management
- Knowledge graph operations

## Features

### SearchAgent
- Web search capabilities using Brave Search API
- Information retrieval and summarization
- Context-aware search results

### ComsAgent
- Email management with support for multiple recipients
- Filesystem operations (read, write, create, delete)
- Knowledge graph memory system for storing and retrieving information
- Entity relationship management

### GitAgent
- GitHub repository operations
- File management
- Commit and push capabilities
- Branch management

## Example Usage

1. Search for information:
```
You: Search for the latest developments in AI
```

2. Send an email:
```
You: Send an email to chris about the AI search results
```

3. Manage files:
```
You: Create a new file with the search results
```

4. GitHub operations:
```
You: Push the new file to the repository
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.
