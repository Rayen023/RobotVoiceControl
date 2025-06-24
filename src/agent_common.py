import os
from typing import Annotated
import time

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
    process_crabs_and_pick,  # ✅ Add this
)

from src.crab_tools import analyze_crab_image
from src.simple_emotion_detector import get_emotion_and_description

TOOLS = [
    get_tech_doc,
    send_movement_command,
    send_pick_and_place_command,
    send_robot_to_initial_home_position,
    get_emotion_and_description,
    check_detected_objects,
    get_current_position,
    analyze_crab_image,
    process_crabs_and_pick,  # ✅ Add this
]

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

Your responses will be converted to speech. Avoid using special characters, markdown syntax, symbols, or emojis. Also don't return the actual position unless the user ask for it.
--- END SYSTEM INSTRUCTIONS ---
"""


class State(TypedDict):
    messages: Annotated[list, add_messages]
    decision_time_ms: int  # 🕒 Add this to track LLM decision time


def setup_agent(chat_llm):
    graph_builder = StateGraph(State)
    graph_builder.add_node("tools", ToolNode(TOOLS))
    def timed_chatbot_node(state):
        start_time = time.time()
        response = chat_llm.bind_tools(TOOLS).invoke([system_prompt, *state["messages"]])
        end_time = time.time()
        duration_ms = int((end_time - start_time) * 1000)

        return {
            "messages": response,
            "decision_time_ms": duration_ms,  # 🕒 Include decision time in output state
        }

    graph_builder.add_node("chatbot", timed_chatbot_node)
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.set_entry_point("chatbot")
    memory = MemorySaver()
    return graph_builder.compile(checkpointer=memory)


graph = setup_agent(chat_llm)
