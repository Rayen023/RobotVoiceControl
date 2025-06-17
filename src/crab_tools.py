from langchain_core.tools import tool

from src.CrabLegClawandSize import process_image

@tool
def analyze_crab_image() -> str:
    """
    Analyzes a crab image to extract features such as the number of legs, claws, carapace width, condition, and quality grade.
    This function prompts the user for the image path, and processes the image to extract relevant features.
    Do not ask the use for the image path as this tool will prompt for it interactively in the console.

    Args:
        image_path (str): The path to the crab image file to analyze.

    Returns:
        str: A summary string containing the extracted crab features and quality assessment.
    """
    image_path = input("Enter the path to the crab image: ")
    if not image_path:
        return "No image path provided. Please enter a valid path."
    
    try:
        return process_image(image_path)
    except Exception as e:
        error_msg = f"{e}"
        print(error_msg)
        return error_msg
