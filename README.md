# Nova Agent: Your Autonomous Local Intelligence

Nova Agent is a powerful, autonomous AI agent designed to run locally, leveraging Google's Gemini models to assist with complex tasks, system interaction, and intelligent decision-making. Built with a modular architecture, it combines the power of LangChain, Pydantic, and Textual for a seamless terminal-based experience.

![Nova Agent Interface](path/to/your/screenshot.png)

## Features
- **Autonomous Execution:** Capable of planning and executing tasks independently.
- **Local-First Design:** Built to run efficiently on your machine.
- **Modular Tools:** Easily extensible toolset for system interaction.
- **Rich UI:** A modern, terminal-based user interface powered by Textual.
- **Memory Management:** Persistent history and context awareness.

## Installation

To get started with Nova Agent, follow these steps:

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/nova-agent.git
cd nova-agent
```

### 2. Install dependencies
This project uses [Poetry](https://python-poetry.org/) for dependency management. Ensure you have it installed, then run:

```bash
poetry install
```

### 3. Configuration
Before running the agent, you need to set up your environment variables.

1. Copy the example environment file (if available) or create a new one:
   ```bash
   cp .env.example .env
   ```
2. Open the `.env` file and add your API keys:
   ```env
   GOOGLE_API_KEY=your_api_key_here
   ```

## Usage
Once installed and configured, you can launch the agent directly from your terminal:

```bash
poetry run nova
```

## Project Structure
- `src/nova_agent/`: Core logic of the agent.
- `src/nova_agent/brain.py`: The decision-making engine.
- `src/nova_agent/tools.py`: Available tools for the agent.
- `src/nova_agent/ui.py`: Terminal user interface.

## License
This project is licensed under the MIT License.
