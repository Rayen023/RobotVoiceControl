from dotenv import load_dotenv
from google import genai

from src.agent_common import graph

load_dotenv()

# Initialize the GenAI client and LLM
genai_client = genai.Client()


def main():
    print("Starting text-based agent...")
    print("Type 'exit' to quit the application.")

    thread_id = "1"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        while True:
            # Get user input from terminal
            user_input = input("\nYou: ")

            # Check if user wants to exit
            if user_input.lower() in ["exit", "quit"]:
                print("\nExiting text-based agent. Goodbye!")
                break

            # Process the user input through the agent
            events = graph.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config,
                stream_mode="values",
            )

            # Display the AI response
            print("\nAI Assistant:", end=" ")
            for event in events:
                event["messages"][-1].pretty_print()

    except KeyboardInterrupt:
        print("\nExiting text-based agent. Goodbye!")


if __name__ == "__main__":
    main()
