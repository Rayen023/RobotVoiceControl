## Overview

Robot Voice Control allows you to interact with and control robot systems through voice recognition. It connects to robot controllers via Telnet and manages robot movements based on spoken instructions.

## Requirements

- Python 3.11+
- Dependencies listed in `pyproject.toml`

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -e .
   ```
3. Create a `.env` file with required API keys

## Usage

Run the voice agent to control robots with voice commands:

```
python voice_agent.py
```

Or use the text-based agent:

```
python text_agent.py
```

## Project Structure

- `voice_agent.py` - Voice recognition and processing
- `text_agent.py` - Text-based command processing
- `src/robot_control.py` - Robot communication and control functions
- `src/agent_tools.py` - Agent utilities and tools