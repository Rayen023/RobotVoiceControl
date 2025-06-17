import os
import platform
from pathlib import Path

from langchain_core.tools import tool

from src.CrabLegClawandSize import process_image


def validate_and_adapt_path(path_input: str, base_dir: str = None) -> dict:
    """
    Validates and adapts a file path to work correctly on the current operating system.
    Handles both relative and absolute paths, and provides detailed information about the path.

    Args:
        path_input (str): The input path to validate and adapt
        base_dir (str, optional): Base directory for relative paths. If None, uses current working directory.

    Returns:
        dict: A dictionary containing:
            - 'original_path': The original input path
            - 'adapted_path': The OS-adapted path
            - 'absolute_path': The absolute version of the path
            - 'exists': Boolean indicating if the path exists
            - 'is_relative': Boolean indicating if the original path was relative
            - 'is_absolute': Boolean indicating if the original path was absolute
            - 'path_type': 'file', 'directory', or 'nonexistent'
            - 'os_format': The operating system format used
            - 'normalized_path': The normalized version of the path
            - 'parent_dir': The parent directory of the path
            - 'filename': The filename (if it's a file)
            - 'extension': The file extension (if it's a file)
    """
    # Get current OS information
    current_os = platform.system().lower()

    # Initialize base directory
    if base_dir is None:
        base_dir = os.getcwd()
    else:
        base_dir = str(Path(base_dir).resolve())

    # Create Path object for cross-platform handling
    path_obj = Path(path_input)

    # Determine if path is relative or absolute
    is_relative = not path_obj.is_absolute()
    is_absolute = path_obj.is_absolute()

    # Handle relative paths
    if is_relative:
        # Convert relative path to absolute using base directory
        absolute_path_obj = Path(base_dir) / path_obj
    else:
        absolute_path_obj = path_obj

    # Resolve the path (handles .. and . components)
    try:
        resolved_path = absolute_path_obj.resolve()
        normalized_path = str(resolved_path)
    except (OSError, ValueError) as e:
        # If path cannot be resolved, use the best approximation
        normalized_path = str(absolute_path_obj)
        resolved_path = absolute_path_obj

    # Convert to OS-appropriate format
    if current_os == "windows":
        adapted_path = str(resolved_path).replace("/", "\\")
        os_format = "Windows"
    else:  # Linux, macOS, etc.
        adapted_path = str(resolved_path).replace("\\", "/")
        os_format = "Unix-like"

    # Check if path exists and determine type
    exists = resolved_path.exists()
    if exists:
        if resolved_path.is_file():
            path_type = "file"
        elif resolved_path.is_dir():
            path_type = "directory"
        else:
            path_type = "other"
    else:
        path_type = "nonexistent"

    # Extract path components
    parent_dir = str(resolved_path.parent)
    filename = resolved_path.name if resolved_path.name != "." else ""
    extension = (
        resolved_path.suffix
        if resolved_path.is_file() or (not exists and resolved_path.suffix)
        else ""
    )

    return {
        "original_path": path_input,
        "adapted_path": adapted_path,
        "absolute_path": str(resolved_path),
        "exists": exists,
        "is_relative": is_relative,
        "is_absolute": is_absolute,
        "path_type": path_type,
        "os_format": os_format,
        "normalized_path": normalized_path,
        "parent_dir": parent_dir,
        "filename": filename,
        "extension": extension,
        "base_dir_used": base_dir,
    }


def get_safe_path(
    path_input: str, base_dir: str = None, create_if_missing: bool = False
) -> str:
    """
    Gets a safe, OS-adapted path and optionally creates missing directories.

    Args:
        path_input (str): The input path to process
        base_dir (str, optional): Base directory for relative paths
        create_if_missing (bool): Whether to create missing parent directories

    Returns:
        str: The safe, adapted path ready for use

    Raises:
        FileNotFoundError: If the path doesn't exist and create_if_missing is False
        PermissionError: If unable to create directories due to permissions
    """
    path_info = validate_and_adapt_path(path_input, base_dir)

    if not path_info["exists"]:
        if create_if_missing:
            # Create parent directories if they don't exist
            parent_path = Path(path_info["parent_dir"])
            try:
                parent_path.mkdir(parents=True, exist_ok=True)
                print(f"Created directory structure: {parent_path}")
            except PermissionError as e:
                raise PermissionError(f"Cannot create directory {parent_path}: {e}")
        else:
            raise FileNotFoundError(f"Path does not exist: {path_info['adapted_path']}")

    return path_info["adapted_path"]


@tool
def analyze_crab_image(image_path: str) -> str:
    """
    Analyzes a crab image to extract features such as the number of legs, claws, carapace width, condition, and quality grade.
    Automatically validates and adapts the image path for the current OS.

    Args:
        image_path (str): The path to the crab image file to analyze.

    Returns:
        str: A summary string containing the extracted crab features and quality assessment.
    """
    try:
        # Validate and adapt the path for the current OS
        safe_path = get_safe_path(image_path)
        print(f"Analyzing crab image at: {safe_path}")
        return process_image(safe_path)
    except (FileNotFoundError, PermissionError) as e:
        error_msg = f"Error accessing image path '{image_path}': {e}"
        print(error_msg)
        return error_msg
