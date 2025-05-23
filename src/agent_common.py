import os
from typing import Annotated

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

load_dotenv()

from src.agent_tools import (
    get_tech_doc,
    send_movement_command,
    send_pick_and_place_command,
    send_robot_to_initial_home_position,
)
from src.simple_emotion_detector import get_emotion_and_description

# chat_llm = ChatGoogleGenerativeAI(
#     model="gemini-2.5-flash-preview-04-17",
#     temperature=0,
#     max_tokens=None,
#     timeout=None,
#     max_retries=2,
# )

chat_llm = ChatOpenAI(
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base=os.getenv("OPENROUTER_BASE_URL"),
    model_name="google/gemini-2.5-flash-preview-05-20",  # "openai/gpt-4o-mini",
    temperature=0,
    max_tokens=8096,
    timeout=None,
    max_retries=2,
    streaming=False,
)

# Shared system prompt
system_prompt = """
You are a helpful assistant for a voice-controlled KUKA robot. Your primary functions are to:
1.  Answer questions and provide information about the robot's capabilities, technical specifications.
2.  Execute robot control commands based on user voice input.

IMPORTANT - SPEECH RECOGNITION HANDLING:
The user input is from voice transcription which may contain errors. You need to:
- Identify and correct potential transcription errors (e.g., "books" instead of "box", "pic" instead of "pick", "build" instead of "bin" etc.)
- Use context to infer the correct meaning of ambiguous commands (e.g., "pick up the box in the bin" instead of "pick up the books to the build")
- Use contextual clues to infer user's true intention (previous messages, robot capabilities)
- When uncertain about ambiguous commands, provide 2-3 likely interpretations and ask for confirmation
- Common transcription errors include: homophones, similar-sounding words, missing words, or joined phrases
- For robot control commands, prioritize safety by confirming potentially risky actions

Remember previous interactions to maintain conversational context.
If a tool call fails, report the error to the user without retrying unless the user request a retry.
"""

# Shared tools list
tools = [
    get_tech_doc,
    send_movement_command,
    send_pick_and_place_command,
    send_robot_to_initial_home_position,
    get_emotion_and_description,
]


class State(TypedDict):
    messages: Annotated[list, add_messages]


def setup_agent(chat_llm):
    graph_builder = StateGraph(State)
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.add_node(
        "chatbot",
        lambda state: {
            "messages": chat_llm.bind_tools(tools).invoke(
                [system_prompt, *state["messages"]]
            )
        },
    )
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.set_entry_point("chatbot")
    memory = MemorySaver()
    return graph_builder.compile(checkpointer=memory)


graph = setup_agent(chat_llm)
