from langchain_core.tools import tool

from src.CrabLegClawandSize import process_image


@tool
def analyze_crab_image(image_path: str) -> str:
    """
    Analyzes a crab image to extract features such as the number of legs, claws, carapace width, condition, and quality grade.

    Args:
        image_path (str): The path to the crab image file to analyze.

    Returns:
        str: A summary string containing the extracted crab features and quality assessment.
    """
    print(f"Analyzing crab image at: {image_path}")
    return process_image(image_path)
