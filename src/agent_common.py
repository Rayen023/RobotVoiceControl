import os
from typing import Annotated

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

load_dotenv()

from src.agent_tools import (
    check_detected_objects,
    get_current_position,
    get_tech_doc,
    send_movement_command,
    send_pick_and_place_command,
    send_robot_to_initial_home_position,
)
from src.simple_emotion_detector import get_emotion_and_description

TOOLS = [
    get_tech_doc,
    send_movement_command,
    send_pick_and_place_command,
    send_robot_to_initial_home_position,
    get_emotion_and_description,
    check_detected_objects,
    get_current_position,
]

chat_llm = ChatOpenAI(
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base=os.getenv("OPENROUTER_BASE_URL"),
    model_name="google/gemini-2.5-flash-preview-05-20",  # "openai/gpt-4o-mini",
    temperature=0,
    max_tokens=8096,
    max_retries=2,
    streaming=False,
)

# Shared system prompt
system_prompt = """
--- START SYSTEM INSTRUCTIONS ---
You are an assistant for a voice-controlled KUKA robot. Your tasks are to:
1. Provide information on the robot’s capabilities and technical specifications.
2. Execute control commands based on the operator’s voice input.

Speech transcription may contain errors. You must:
• Correct likely mistakes (e.g., “books” vs. “box”, “pic” vs. “pick”, “build” vs. “bin”).
• Use context to resolve ambiguities and infer the true intent.
• If uncertain, offer two to three interpretations and request confirmation.
• Prioritize safety by confirming any potentially risky actions.

Maintain conversational context throughout interactions.
If a tool call fails, report the error without retrying unless explicitly asked.

Your responses will be converted to speech. Avoid using special characters, markdown syntax, symbols, or emojis.
--- END SYSTEM INSTRUCTIONS ---
"""


class State(TypedDict):
    messages: Annotated[list, add_messages]


def setup_agent(chat_llm):
    graph_builder = StateGraph(State)
    graph_builder.add_node("tools", ToolNode(TOOLS))
    graph_builder.add_node(
        "chatbot",
        lambda state: {
            "messages": chat_llm.bind_tools(TOOLS).invoke(
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
