import os

from langchain_core.tools import tool

from src.CrabLegClawandSize import process_image


@tool
def analyze_crab_image(image_path: str = None) -> str:
    """
    Analyzes a crab image to extract features like leg count, claw count, carapace width,
    shell condition, and quality grade using computer vision models.
    Do not ask the usee for the image path as this tool will prompt for it interactively in the console/terminal.

    Args:
        image_path (str, optional): Path to the crab image. If not provided,
                                   prompts the user for input interactively.

    Returns:
        str: Summary of crab features and quality assessment, or error message if processing fails.
    """
    try:
        if image_path is None:
            image_path = input("Enter the path to the crab image: ").strip()

        if not image_path:
            return "Error: No image path provided."

        # Check if file exists and is readable
        if not os.path.exists(image_path):
            return f"Error: Image file not found: {image_path}"
        print(f"Successfully found image: {image_path}")

        return process_image(image_path)

    except Exception as e:
        return f"Error: {str(e)}"
