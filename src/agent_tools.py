import json
import os
import time
import glob
from src.CrabLegClawandSize import process_image
from src.crab_tools import parse_crab_analysis  # <- uses the parsing function added above


from langchain_core.tools import tool

from src.robot_control import (
    COGNEX_IP,
    FTP_PASS,
    FTP_USER,
    PLACE_POSITIONS,
    ROBOT_IP,
    ROBOT_PORT,
    cartesian_movement,
    compute_rotated_tool_offset,
    connect_to_robot,
    control_gripper,
    fetch_cognex_patterns,
    pick_and_place,
    trigger_camera,
    wait_for_target_position,
)

file_path = os.path.join("src", "tech_doc.md")

with open(file_path, "r", encoding="utf-8") as file:
    content = file.read()

client = connect_to_robot(ROBOT_IP, ROBOT_PORT)


def parse_position_data(pos_string):
    """Helper function to parse robot position data into a dictionary"""
    pos_data = pos_string.strip("{}").replace("E6POS:", "").split(",")
    return {
        item.split()[0]: float(item.split()[1])
        for item in pos_data
        if len(item.split()) == 2
    }


def positions_equal(pos1, pos2, tolerance=0.1):
    """Check if two positions are equal within tolerance"""
    for axis in ["X", "Y", "Z"]:
        if abs(pos1.get(axis, 0) - pos2.get(axis, 0)) > tolerance:
            return False
    return True


@tool
def get_tech_doc() -> str:
    """
    Retrieves technical characteristics of the robot.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()
    return content


@tool
def send_robot_to_initial_home_position() -> str:
    """
    Sends the robot to its predefined home position and waits until the robot confirms it has reached the target.

    Returns:
        str: Success message if the operation completed successfully,
             or an error message with details about the failure point if an exception occurred.
    """
    try:
        client = connect_to_robot(ROBOT_IP, ROBOT_PORT)

        # Get initial position
        initial_pos_str = client.read("$POS_ACT", debug=True).decode("utf-8")
        initial_pos = parse_position_data(initial_pos_str)

        cartesian_movement(
            client, 1332.63, 0, 1270, 178.75, 0, -179.91, Move="PTP"
        )  # Adjust Z value
        wait_for_target_position(
            client,
            target_position={"X": 1332.63, "Y": 0, "Z": 1270},
            timeout=30,
            tolerance=0.5,
        )
        time.sleep(0.5)

        # Get final position and check if robot moved
        final_pos_str = client.read("$POS_ACT", debug=True).decode("utf-8")
        final_pos = parse_position_data(final_pos_str)

        if positions_equal(initial_pos, final_pos):
            raise Exception("Was not able to move the robot")

        return "Success: Robot moved to initial home position"
    except Exception as e:
        error_msg = f"Failed to move robot to home position: {str(e)}"
        print(error_msg)
        return error_msg


@tool
def get_current_position() -> str:
    """
    Returns the current poistion of the robot

    Returns:
        str: Either an Error message if an exception occurred or the current coordinates of the robot.
    """
    try:
        client = connect_to_robot(ROBOT_IP, ROBOT_PORT)
        # client = connect_to_robot(ROBOT_IP, ROBOT_PORT)
        current_pos = client.read("$POS_ACT", debug=True).decode("utf-8")
        # print(f"Current position: {current_pos}")
        current_data = current_pos.strip("{}").replace("E6POS:", "").split(",")
        # print(f"Current data: {current_data}")
        pos_dict = {
            item.split()[0]: float(item.split()[1])
            for item in current_data
            if len(item.split()) == 2
        }

        return f"The current coordinates of the robot : X : {pos_dict["X"]}, Y : {pos_dict["Y"]}, Z : {pos_dict["Z"]}, A : {pos_dict["A"]}, B : {pos_dict["B"]}, C : {pos_dict["C"]}"
    except Exception as e:
        error_msg = f"Failed to get coordinates : {str(e)}"
        print(error_msg)
        return error_msg


@tool
def send_movement_command(
    X: int = 0, Y: int = 0, Z: int = 0, A: int = 0, B: int = 0, C: int = 0
) -> str:
    """
    Moves the robot by the specified relative distance along each axis in millimeters.

    Args:
        X (int, optional): Relative movement along X-axis in mm. Positive = forward, negative = backward. Defaults to 0.
        Y (int, optional): Relative movement along Y-axis in mm. Positive = left, negative = right. Defaults to 0.
        Z (int, optional): Relative movement along Z-axis in mm. Positive = up, negative = down. Defaults to 0.
        A (int, optional): Relative rotation around X-axis in degrees. Defaults to 0.
        B (int, optional): Relative rotation around Y-axis in degrees. Defaults to 0.
        C (int, optional): Relative rotation around Z-axis in degrees. Defaults to 0.

    Returns:
        str: Success message with final position coordinates if operation completed successfully,
             or an error message if the movement is blocked due to collision risk or with details about the failure point if an exception occurred.

    Examples:
        - "Move forward 20cm" → X=200
        - "Go backward 30cm" → X=-300
        - "Move up 10cm" → Z=100
        - "Go down 15cm" → Z=-150
        - "Move left 10cm" → Y=100
        - "Go right 15cm" → Y=-150

    Example:
        >>> send_movement_command(X=100, Z=50)
        'Success: Robot moved to position X:1532.0, Y:245.0, Z:1350.0'

    You will receive a voice command describing a shape to draw (square, rectangle, triangle), along with optional dimensions and directions.
    You should also interpret command like sweep, zigzag, L-shape, semi-rectangle, W-shape, a star, ect. You should then move the robot accordingly, always use small movements of 10-20 cm.

    Examples:
        - A square is drawn on two axes (e.g., X and Y), moving equal lengths:
        1. +X, then +Y, then -X, then -Y. You should send the movement one after the other.
        - A rectangle has unequal lengths on two axes:
        1. +X (width), then +Y (height), then -X, then -Y.
        - A triangle is an isosceles triangle on two axes (e.g., X/Y or Y/Z):
        1. Diagonal up right (+X, +Y), then diagonal up left (-X, +Y), then vertical down (Y-)        - If no plane is specified, assume X and Y
    """
    try:
        client = connect_to_robot(ROBOT_IP, ROBOT_PORT)

        print(X, Y, Z)
        # Get initial position
        initial_pos_str = client.read("$POS_ACT", debug=True).decode("utf-8")
        initial_pos = parse_position_data(initial_pos_str)

        pos_dict = initial_pos.copy()

        movement = {
            "X": X,
            "Y": Y,
            "Z": Z,
            "A": A,
            "B": B,
            "C": C,
        }

        for axis, val in movement.items():
            pos_dict[axis] += val

        cartesian_movement(
            client,
            pos_dict["X"],
            pos_dict["Y"],
            pos_dict["Z"],
            pos_dict["A"],
            pos_dict["B"],
            pos_dict["C"],
            Move="PTP",
        )

        wait_for_target_position(
            client,
            target_position={
                "X": pos_dict["X"],
                "Y": pos_dict["Y"],
                "Z": pos_dict["Z"],
            },
            timeout=30,
            tolerance=0.5,
        )
        time.sleep(0.5)

        # Get final position and check if robot moved
        final_pos_str = client.read("$POS_ACT", debug=True).decode("utf-8")
        final_pos = parse_position_data(final_pos_str)

        if positions_equal(initial_pos, final_pos):
            raise Exception("Was not able to move the robot")

        return f"Success: Robot moved to position X:{pos_dict['X']}, Y:{pos_dict['Y']}, Z:{pos_dict['Z']}"
    except Exception as e:
        error_msg = f"Failed to move robot: {str(e)}"
        print(error_msg)
        return error_msg


@tool
def send_pick_and_place_command(item2pick: str, location2place: str) -> str:
    """
    Executes a complete pick and place operation using computer vision and robot control.

    Args:
        item2pick (str): The item to pick up. Must be either "box" or "wood" or "orange box".
        location2place (str): The destination location. Must be either "bin" or "Conveyor".

    Returns:
        str: Success message if the operation completed successfully,
             or an error message with details about the failure point if an exception occurred.

    Example:
        >>> send_pick_and_place_command("box", "conveyor")        'Success: Picked box and placed at conveyor'
    """
    try:
        client = connect_to_robot(ROBOT_IP, ROBOT_PORT)

        # Get initial position
        initial_pos_str = client.read("$POS_ACT", debug=True).decode("utf-8")
        initial_pos = parse_position_data(initial_pos_str)

        # Trigger camera and get vision data
        trigger_camera(COGNEX_IP, FTP_USER, FTP_PASS)
        time.sleep(2)

        box_pattern, wood_pattern, orange_box_pattern = fetch_cognex_patterns()
        print(
            f"✅ Patterns: Box={box_pattern}, Wood={wood_pattern}, OrangeBox={orange_box_pattern}"
        )

        # Determine place location
        if "bin" in location2place:
            place_coords = PLACE_POSITIONS["bin"]
        else:
            place_coords = PLACE_POSITIONS["Conveyor"]

        # Select pattern based on item type
        if item2pick == "box":
            if (
                box_pattern
                and float(box_pattern["X"]) > 0
                and float(box_pattern["Y"]) > 0
            ):
                pattern = box_pattern
                pick_z = 1075
            else:
                return "Failed: Box pattern not detected by camera"
        elif item2pick == "wood":
            if (
                wood_pattern
                and float(wood_pattern["X"]) > 0
                and float(wood_pattern["Y"]) > 0
            ):
                pattern = wood_pattern
                pick_z = 1054
            else:
                return "Failed: wood pattern not detected by camera"
        elif item2pick == "orange box":
            if (
                orange_box_pattern
                and float(orange_box_pattern["X"]) > 0
                and float(orange_box_pattern["Y"]) > 0
            ):
                pattern = orange_box_pattern
                pick_z = 1065
        else:
            return f"Failed: Unknown item type '{item2pick}'"

        if not pattern:
            return f"Failed: {item2pick} pattern not detected by camera"

        pick_x, pick_y, pick_a = pattern["X"], pattern["Y"], pattern["Angle"]

        tool_offset = {"X": 0, "Y": 0, "Z": 0, "A": 0, "B": 0, "C": 0}

        pick_and_place(
            client, pick_x, pick_y, pick_z, pick_a, tool_offset, place_coords
        )

        control_gripper(client, "open")

        # Get final position and check if robot moved
        final_pos_str = client.read("$POS_ACT", debug=True).decode("utf-8")
        final_pos = parse_position_data(final_pos_str)

        if positions_equal(initial_pos, final_pos):
            raise Exception("Was not able to move the robot")

        return f"Success: Picked {item2pick} and placed at {location2place}"

    except Exception as e:
        error_msg = f"Failed during pick and place operation: {str(e)}"
        print(error_msg)
        return error_msg

@tool
def process_crabs_and_pick(
    _: str = "",
    condition: str = "",
    location: str = "Conveyor",
    min_legs: int = None,
    max_legs: int = None,
    min_claws: int = None,
    max_claws: int = None,
    min_size: float = None,
    max_size: float = None,
    shell_condition: str = None
) -> str:
    """
    Prompts user to enter crab image paths one-by-one and evaluates each crab against the provided filters.
    Type 'q' to stop.

    Args:
        condition (str): Quality grade (e.g., 'Premium', 'Grade A'). Optional.
        location (str): Destination for pick-and-place ('Conveyor' or 'bin').
        min_legs, max_legs (int): Leg count filter (0 to 8).
        min_claws, max_claws (int): Claw count filter (0 to 2).
        min_size, max_size (float): Carapace width range in cm.
        shell_condition (str): 'Soft' or 'Hard' shell. Optional.

    Returns:
        str: Summary of evaluations.
    """

    # ✅ Cap invalid biological values
    if min_legs is not None and min_legs > 8:
        print("⚠️ Crabs have max 8 legs. Adjusting min_legs to 8.")
        min_legs = 8
    if max_legs is not None and max_legs > 8:
        max_legs = 8
    if min_claws is not None and min_claws > 2:
        print("⚠️ Crabs have max 2 claws. Adjusting min_claws to 2.")
        min_claws = 2
    if max_claws is not None and max_claws > 2:
        max_claws = 2

    results = []

    print(f"\n📂 Starting crab inspection loop → location: '{location}'.")
    print("📸 Enter image path (or 'q' to quit):")

    while True:
        image_path = input("→ Image path: ").strip()

        if image_path.lower() == "q":
            print("👋 Exiting crab processing loop.")
            break

        if not os.path.isfile(image_path):
            print("❌ Invalid path. Please try again.")
            continue

        try:
            result_str = process_image(image_path)
            crab_data = parse_crab_analysis(result_str)

            criteria = []

            if min_legs is not None:
                criteria.append(crab_data["legs"] >= min_legs)
            if max_legs is not None:
                criteria.append(crab_data["legs"] <= max_legs)

            if min_claws is not None:
                criteria.append(crab_data["claws"] >= min_claws)
            if max_claws is not None:
                criteria.append(crab_data["claws"] <= max_claws)

            if min_size is not None:
                criteria.append(crab_data["carapace_width_cm"] >= min_size)
            if max_size is not None:
                criteria.append(crab_data["carapace_width_cm"] <= max_size)

            if shell_condition is not None:
                criteria.append(
                    crab_data["carapace_condition"].lower() == shell_condition.lower()
                )

            if condition:
                criteria.append(
                    crab_data["quality_grade"].lower() == condition.lower()
                )

            match = all(criteria)

            if match:
                message = f"{os.path.basename(image_path)} → ✅ Crab matches criteria. Robot is ready for pick and place."
            else:
                message = f"{os.path.basename(image_path)} → ❌ Does not match requested criteria"

            print(message)
            results.append(message)

        except Exception as e:
            err_msg = f"{os.path.basename(image_path)} → ⚠️ Error: {e}"
            print(err_msg)
            results.append(err_msg)

    return "\n".join(results)

@tool
def check_detected_objects() -> str:
    """
    Captures an image of the conveyor belt and detects objects present using the conveyor-mounted camera.
    Use this tool when the user asks what items are on the conveyor, what can be picked, or requests an inventory of conveyor objects.

    Returns:
        str: A message listing detected objects with their coordinates and angles, e.g.,
             "Objects detected in image: box at X:123.4, Y:56.7, Angle:0.0°, wood at X:...", or
             "No objects detected on the conveyor" if none are found.
    """
    try:
        # Trigger camera and get vision data
        trigger_camera(COGNEX_IP, FTP_USER, FTP_PASS)
        time.sleep(2)

        box_pattern, wood_pattern, orange_box_pattern = fetch_cognex_patterns()
        print(
            f"✅ Patterns: Box={box_pattern}, Wood={wood_pattern}, OrangeBox={orange_box_pattern}"
        )  # Define pattern mappings with their names
        patterns = {
            "box": box_pattern,
            "wood": wood_pattern,
            "orange box": orange_box_pattern,
        }  # Check which objects are properly detected
        detected_objects = {}
        for object_name, pattern in patterns.items():
            if pattern and float(pattern["X"]) > 0 and float(pattern["Y"]) > 0:
                detected_objects[object_name] = pattern

        if detected_objects:
            # Format output with coordinates and angle
            object_descriptions = []
            for obj_name, pattern in detected_objects.items():
                object_descriptions.append(
                    f"{obj_name} at X:{pattern['X']:.1f}, Y:{pattern['Y']:.1f}, Angle:{pattern['Angle']:.1f}°"
                )

            result = f"Objects detected in image: {', '.join(object_descriptions)}"
            print(result)
            return result
        else:
            return "No objects detected in image"

    except Exception as e:
        error_msg = f"Failed to check detected objects: {str(e)}"
        print(error_msg)
        return error_msg
