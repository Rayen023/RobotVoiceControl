import os

from langchain_core.tools import tool

from src.CrabLegClawandSize import process_image
import re


@tool
def analyze_crab_image(image_path: str = None) -> str:
    """
    Analyzes a crab image to extract features like leg count, claw count, carapace width,
    Soft shell crabs are clean and without barcnacles, while hard shell crabs may have barnacles and are dirty.
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
    
    

def parse_crab_analysis(text: str) -> dict:
    """
    Parses the crab analysis string into a structured dictionary.
    Example: "Legs: 8, Claws: 2, Carapace Width: 10.50 cm, Condition: soft, Quality: Premium"
    """
    try:
        pattern = r"Legs: (\d+), Claws: (\d+), Carapace Width: ([\d.]+) cm, Condition: (\w+), Quality: ([\w\s]+)"
        match = re.match(pattern, text)
        if not match:
            raise ValueError("Invalid format")

        return {
            "legs": int(match.group(1)),
            "claws": int(match.group(2)),
            "carapace_width": float(match.group(3)),
            "shell_condition": match.group(4).capitalize(),
            "quality_grade": match.group(5).strip().capitalize(),
        }
    except Exception as e:
        raise ValueError(f"Parsing error: {e}")
