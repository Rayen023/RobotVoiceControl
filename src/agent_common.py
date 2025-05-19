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
    model_name="google/gemini-2.5-flash-preview",  # "openai/gpt-4o-mini",
    temperature=0,
    max_tokens=8096,
    timeout=None,
    max_retries=2,
    streaming=False,
)

# Shared system prompt
system_prompt = """
You are a helpful assistant named kuka assistant. You can answer questions and provide information.
You can also use tools to help you find information when needed.
You can ask me to use a tool if you need help with something specific.
If a tool call fails, return the output of the tool call to the user, do not retry the tool call.
You have access to conversational memory, which allows you to remember previous interactions.
"""

# Shared tools list
tools = [
    get_tech_doc,
    send_movement_command,
    send_pick_and_place_command,
    send_robot_to_initial_home_position,
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
