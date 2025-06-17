from langchain_core.tools import tool

from src.CrabLegClawandSize import process_image


@tool
def analyze_crab_image() -> str:
    """
    Analyzes a crab image to extract features such as the number of legs, claws, carapace width, condition, and quality grade.

    When the LLM is asked to analyze a crab, it should call this tool directly without asking the user for the image path.
    The tool will prompt for the image path in the terminal and pass it directly to the models for processing.

    The function will wait for user input in the terminal, process the image, and return a summary string containing
    the extracted crab features and quality assessment.

    Returns:
        str: A summary string containing the extracted crab features and quality assessment.
    """
    image_path = input("Enter the path to the crab image: ").strip()
    return process_image(image_path)
