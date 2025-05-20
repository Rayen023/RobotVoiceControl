import os
import time

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

        # client = connect_to_robot(ROBOT_IP, ROBOT_PORT)
        cartesian_movement(
            client, 1432, 245, 1300, 178, 0, 180, Move="PTP"
        )  # Adjust Z value
        wait_for_target_position(
            client,
            target_position={"X": 1432, "Y": 245, "Z": 1300},
            timeout=30,
            tolerance=0.5,
        )
        time.sleep(0.5)
        return "Success: Robot moved to initial home position"
    except Exception as e:
        error_msg = f"Failed to move robot to home position: {str(e)}"
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
             or an error message with details about the failure point if an exception occurred.

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
    """
    try:
        client = connect_to_robot(ROBOT_IP, ROBOT_PORT)

        #try:
        print(X,Y,Z)
        # client = connect_to_robot(ROBOT_IP, ROBOT_PORT)
        current_pos = client.read("$POS_ACT", debug=True).decode("utf-8")
        #print(f"Current position: {current_pos}")
        current_data = current_pos.strip("{}").replace("E6POS:", "").split(",")
        #print(f"Current data: {current_data}")
        pos_dict = {
            item.split()[0]: float(item.split()[1])
            for item in current_data
            if len(item.split()) == 2
        }
        #print(f"Position dictionary: {pos_dict}")
        movement = {
            "X": X,
            "Y": Y,
            "Z": Z,
            "A": A,
            "B": B,
            "C": C,
        }
        #print(f"Movement dictionary: {movement}")

        for axis, val in movement.items():
            pos_dict[axis] += val
        #print(f"New position dictionary: {pos_dict}")

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
        item2pick (str): The item to pick up. Must be either "box" or "wood".
        location2place (str): The destination location. Must be either "bin" or "conveyor".

    Returns:
        str: Success message if the operation completed successfully,
             or an error message with details about the failure point if an exception occurred.

    Example:
        >>> send_pick_and_place_command("box", "blue bin")
        'Success: Picked box and placed at blue bin'
    """
    try:
        client = connect_to_robot(ROBOT_IP, ROBOT_PORT)

        # Trigger camera and get vision data
        trigger_camera(COGNEX_IP, FTP_USER, FTP_PASS)
        time.sleep(2)
        event, box_pattern, wood_pattern = fetch_cognex_patterns()
        print(f"✅ Event={event}, box_pattern={box_pattern}, wood_pattern={wood_pattern}")

        if event is None:
            return "Failed: Could not fetch camera patterns"

        # Determine place location
        if "bin" in location2place:
            location2place_coords = PLACE_POSITIONS["blue bin"]
        else:
            location2place_coords = PLACE_POSITIONS["Conveyor"]

        # Select pattern based on item type
        if item2pick == "box":
            if box_pattern and float(box_pattern['X']) > 0 and float(box_pattern['Y']) > 0 : 
                pattern = box_pattern
            else :
                return "Failed: Box pattern not detected by camera"
            pick_z = 1060
        elif item2pick == "wood":
            if wood_pattern and float(wood_pattern['X']) > 0 and float(wood_pattern['Y']) > 0 : 
                pattern = wood_pattern
            else :
                return "Failed: wood pattern not detected by camera"
            pick_z = 1046
            pattern = wood_pattern
        else:
            return f"Failed: Unknown item type '{item2pick}'"

        pick_x, pick_y, pick_coords_angle = pattern["X"] , pattern["Y"], pattern["Angle"]

        tool_offset = {"X": -56.5, "Y": 23.7, "Z": 0, "A": 0, "B": 0, "C": 0}

        pick_and_place(
            client,
            pick_x,
            pick_y,
            pick_z,
            pick_coords_angle,
            tool_offset,
            location2place_coords,
        )

        control_gripper(client, "open")
        #send_robot_to_initial_home_position()  # initialized as tool so cannot pass as function

        return f"Success: Picked {item2pick} and placed at {location2place}"

    except Exception as e:
        error_msg = f"Failed during pick and place operation: {str(e)}"
        print(error_msg)
        return error_msg
