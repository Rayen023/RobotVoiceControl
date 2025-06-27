import csv
import io
import math
import os
import socket
import telnetlib
import time
from ftplib import FTP_TLS

from dotenv import load_dotenv

load_dotenv()
if os.environ.get("USE_PY_OPENSHOWVAR") == "0":

    class openshowvar:
        def __init__(self, ip, port):
            self.ip = ip
            self.port = port
            self.can_connect = True
            print(f"Mock robot connection to {ip}:{port} initialized")

        def read(self, variable, debug=False):
            if debug:
                print(f"Mock reading {variable}")
            # Return a mock position for $POS_ACT
            if variable == "$POS_ACT":
                return b"E6POS: X 500.0, Y 300.0, Z 1200.0, A 180.0, B 0.0, C 180.0"
            return b"0"

        def write(self, variable, value, debug=False):
            if debug:
                print(f"Mock writing {value} to {variable}")
            return True

else:
    from py_openshowvar import openshowvar


# === IP Configurations ===
COGNEX_IP = "192.169.2.99"
ROBOT_IP = "192.169.2.100"
ROBOT_PORT = 7000

# === FTP/Cognex Config
FTP_USER = "admin"
FTP_PASS = ""
FTP_CSV_FOLDER = "sdcard"
CSV_FILENAME = "DemoResults.csv"


# === Collision Zones ===
COLLISION_ZONES = [
    {
        "name": "camera_support",
        "min": {"X": 1250, "Y": 950, "Z": -999999},
        "max": {"X": 1700, "Y": 999999, "Z": 999999},
    },
    {
        "name": "conveyor_zone",
        "min": {"X": 990, "Y": -999999, "Z": -999999},
        "max": {"X": 1870, "Y": 999999, "Z": 1010},
    },
    {
        "name": "ceiling_camera",
        "min": {"X": 1290, "Y": 490, "Z": 1800},
        "max": {"X": 1700, "Y": 950, "Z": 999999},
    },
]
COLLISION_MARGIN = 0


def is_in_collision_zone(position: dict, client: openshowvar = None) -> None:
    """
    Check if the given position is inside any defined collision zone,
    considering a safety margin in all directions. Raises an error if collision detected.

    Args:
        position (dict): Position dictionary with X, Y, Z.
        client (openshowvar, optional): Robot client for sending interrupt commands.

    Returns:
        None

    Raises:
        ValueError: If position is in a collision zone.
    """
    for zone in COLLISION_ZONES:
        min_x = zone["min"]["X"] - COLLISION_MARGIN
        max_x = zone["max"]["X"] + COLLISION_MARGIN
        min_y = zone["min"]["Y"] - COLLISION_MARGIN
        max_y = zone["max"]["Y"] + COLLISION_MARGIN
        min_z = zone["min"]["Z"] - COLLISION_MARGIN
        max_z = zone["max"]["Z"] + COLLISION_MARGIN

        if (
            min_x <= position["X"] <= max_x
            and min_y <= position["Y"] <= max_y
            and min_z <= position["Z"] <= max_z
        ):
            print(
                f"Position {position} is inside or near collision zone: {zone['name']}"
            )
            read_value = client.read("$OUT[17]", debug=True)
            print(f"Interrupt signal read: {read_value}")

            client.write("$OUT[17]", "TRUE", debug=True)
            time.sleep(0.1)
            read_value = client.read("$OUT[17]", debug=True)
            print(f"Interrupt signal read: {read_value}")

            raise ValueError(f"❌ Collision risk detected in zone: {zone['name']}")


def trigger_camera(ip: str, user: str, password: str) -> None:
    """
    Trigger the Cognex camera via Telnet connection.

    Args:
        ip (str): IP address of the camera
        user (str): Username for telnet login
        password (str): Password for telnet login

    Returns:
        None

    Raises:
        Exception: If connection to camera fails or command execution fails
    """
    try:
        # Use Python's standard telnetlib module for synchronous connection
        tn = telnetlib.Telnet(ip, 23, timeout=5)
        time.sleep(0.1)
        tn.write(f"{user}\r\n".encode("ascii"))
        time.sleep(0.1)
        tn.write(("\r\n" if not password else f"{password}\r\n").encode("ascii"))
        time.sleep(0.1)
        tn.write("SE8\r\n".encode("ascii"))
        time.sleep(0.5)
        print("✅ Camera triggered successfully via Telnet.")
        tn.close()
    except Exception as e:
        error_msg = f"❌ Telnet trigger failed: {e}"
        print(error_msg)
        raise Exception(f"Camera trigger failed: {str(e)}")


def fetch_cognex_patterns() -> tuple[dict, dict, dict]:
    """
    Fetch the latest event and pattern data from the Cognex camera via FTP and CSV file.

    Returns:
        tuple: Contains:
            - pattern wood (dict): First pattern with X, Y, Angle or None if not detected
            - pattern box (dict): Second pattern with X, Y, Angle or None if not detected
            - pattern orange_box (dict): Second pattern with X, Y, Angle or None if not detected

    Raises:
        ValueError: If CSV is empty or has invalid format
        Exception: For FTP connection or other errors
    """
    try:
        ftps = FTP_TLS(COGNEX_IP)
        ftps.login(FTP_USER, FTP_PASS)
        ftps.prot_p()
        ftps.cwd(FTP_CSV_FOLDER)
        lines = []
        ftps.retrlines(f"RETR {CSV_FILENAME}", lines.append)
        rows = list(csv.reader(io.StringIO("\n".join(lines))))
        if not rows:
            error_msg = "⚠️ CSV empty."
            print(error_msg)
            raise ValueError(error_msg)
        last_row = rows[-1]
        if len(last_row) < 10:
            raise ValueError("⚠️ CSV format error.")

        def parse_pattern(event_idx, x_idx, y_idx, a_idx):
            event = int(last_row[event_idx])
            if event != 0 and last_row[x_idx] and last_row[y_idx]:
                return {
                    "X": float(last_row[x_idx]),
                    "Y": float(last_row[y_idx]),
                    "Angle": float(last_row[a_idx]),
                }
            return None

        box_pattern = parse_pattern(0, 1, 2, 3)
        wood_pattern = parse_pattern(4, 5, 6, 7)
        orange_box_pattern = parse_pattern(8, 9, 10, 11)

        print(
            f"✅ Patterns: Box={box_pattern}, Wood={wood_pattern}, OrangeBox={orange_box_pattern}"
        )
        return box_pattern, wood_pattern, orange_box_pattern

    except Exception as e:
        error_msg = f"❌ FTP Error: {e}"
        print(error_msg)
        raise Exception(f"Failed to fetch patterns: {str(e)}")


def connect_to_robot(ip: str, port: int) -> openshowvar:
    """
    Establish connection to KUKA robot controller.

    Args:
        ip (str): IP address of the robot controller
        port (int): Port number for the connection

    Returns:
        openshowvar: Client object if connection successful, None otherwise
    """
    client = openshowvar(ip, port)
    if client.can_connect:
        print(f"✅ Connected to KUKA Robot at {ip}:{port}")
    else:
        print("❌ Could not connect to robot.")
        client = None
    return client


def cartesian_movement(
    client: openshowvar,
    x: int = 0,
    y: int = 0,
    z: int = 0,
    a: int = 0,
    b: int = 0,
    c: int = 0,
    Move_type: str = "PTP",
    tool_frame: dict = None,
) -> None:
    """
    Send cartesian movement command to the robot.

    Args:
        client (openshowvar): Robot client object
        x (int): X position coordinate
        y (int): Y position coordinate
        z (int): Z position coordinate
        a (int): A rotation angle
        b (int): B rotation angle
        c (int): C rotation angle
        Move_type (str, optional): Specifies the movement type. Defaults to "PTP". Accepts either "PTP" or "LIN". Pass "LIN" if specified by the user.
        tool_frame (dict): Tool frame offset values
    Returns:
        None
    """
    if client is None:
        raise ValueError("Robot client is not connected")

    tool_frame = tool_frame or {"X": 0, "Y": 0, "Z": 0, "A": 0, "B": 0, "C": 0}

    # Calculate final position including tool frame offset
    final_position = {
        "X": x + tool_frame["X"],
        "Y": y + tool_frame["Y"],
        "Z": z + tool_frame["Z"],
    }  # Check if final position is in collision zone before moving
    is_in_collision_zone(final_position, client)

    new_pos = f"{{X {final_position['X']:.3f}, Y {final_position['Y']:.3f}, Z {final_position['Z']:.3f}, A {a+tool_frame['A']:.3f}, B {b+tool_frame['B']:.3f}, C {c+tool_frame['C']:.3f}}}"
    client.write(
        "COM_E6POS", new_pos, debug=True
    )  # Set target position for CASE 3 LIN movement

    client.write("$VEL.CP", "0.1", debug=True)  # Set Cartesian path velocity (m/s)

    client.write("$ACC.CP", "0.1", debug=True)  # Set Cartesian path acceleration (m/s²)

    # client.write("$MOVE_CMD", Move_type, debug=True)  # Store movement type for reference
    
    if Move_type == "PTP":
        client.write(
            "COM_ACTION", "4", debug=True
        )  # Trigger CASE 2: Move PTP (PTP COM_E6POS)
    elif Move_type == "LIN":
        client.write(
            "COM_ACTION", "3", debug=True
        )  # Trigger CASE 3: Move Linear (LIN COM_E6POS)

    print(f"🚀 Moving to {new_pos}")


def control_gripper(client: openshowvar, state: str) -> None:
    """
    Control the gripper state based on 'open' or 'close'.

    Args:
        client (openshowvar): Robot client object
        state (str): Desired gripper state ('open' or 'close')

    Returns:
        None
    """
    if state == "close":
        # Close the gripper (Set OUT 15 to TRUE and OUT 16 to FALSE)
        client.write(
            "COM_ACTION", "10", debug=True
        )  # Trigger CASE 10: Set Digital Output
        client.write("COM_VALUE1", "15", debug=True)  # Set output pin number (OUT 15)
        client.write("COM_VALUE2", "0", debug=True)  # Set OUT 15 to FALSE
        client.write(
            "COM_ACTION", "10", debug=True
        )  # Trigger CASE 10: Set Digital Output
        client.write("COM_VALUE1", "16", debug=True)  # Set output pin number (OUT 16)
        client.write("COM_VALUE2", "0", debug=True)  # Set OUT 16 to FALSE
        print("Gripper is CLOSED.")

    elif state == "open":
        # Open the gripper (Set OUT 15 to TRUE and OUT 16 to TRUE)
        client.write(
            "COM_ACTION", "10", debug=True
        )  # Trigger CASE 10: Set Digital Output
        client.write("COM_VALUE1", "15", debug=True)  # Set output pin number (OUT 15)
        client.write("COM_VALUE2", "1", debug=True)  # Set OUT 15 to TRUE
        client.write(
            "COM_ACTION", "10", debug=True
        )  # Trigger CASE 10: Set Digital Output
        client.write("COM_VALUE1", "16", debug=True)  # Set output pin number (OUT 16)
        client.write("COM_VALUE2", "0", debug=True)  # Set OUT 16 to FALSE
        print("Gripper is OPEN.")

    else:
        print("Invalid gripper state. Use 'open' or 'close'.")

    time.sleep(1)


def compute_rotated_tool_offset(tool_offset: dict, angle_deg: float) -> dict:
    """
    Compute tool offset after rotation by the specified angle.

    Args:
        tool_offset (dict): Tool offset values with X, Y, Z, A, B, C keys
        angle_deg (float): Rotation angle in degrees

    Returns:
        dict: Rotated tool offset values
    """
    dx = tool_offset.get("X", 0)
    dy = tool_offset.get("Y", 0)
    dz = tool_offset.get("Z", 0)

    angle_rad = math.radians(angle_deg)

    dx_rot = dx * math.cos(angle_rad) - dy * math.sin(angle_rad)
    dy_rot = dx * math.sin(angle_rad) + dy * math.cos(angle_rad)

    return {
        "X": dx_rot,
        "Y": dy_rot,
        "Z": dz,
        "A": tool_offset.get("A", 0),
        "B": tool_offset.get("B", 0),
        "C": tool_offset.get("C", 0),
    }


def parse_robot_data(data):
    # Join all list elements into a single string, then strip the braces
    full_string = " ".join(data).strip("{}")
    items = full_string.split()

    # Pair every two items (key and value)
    result = {items[i]: float(items[i + 1]) for i in range(0, len(items), 2)}
    return result


def wait_for_target_position(
    client: openshowvar,
    target_position: dict,
    timeout: float = 10,
    tolerance: float = 0.1,
    tool_frame: dict = None,
) -> None:
    """
    Wait until the robot's position matches the target position within a given tolerance.
    Exits if robot position doesn't change for the timeout duration.

    Args:
        client (openshowvar): Robot client object
        target_position (dict): Target position with X, Y, Z coordinates
        timeout (float): Maximum time in seconds to wait without position change
        tolerance (float): Acceptable position error
        tool_frame (dict): Tool offset values

    Returns:
        None
    """
    if client is None:
        raise ValueError("Robot client is not connected")

    if not all(key in target_position for key in ["X", "Y", "Z"]):
        raise ValueError("Target position must contain X, Y, and Z coordinates")

    # Apply tool offset if provided
    if tool_frame:
        tool_offsets = {key: tool_frame.get(key, 0) for key in ["X", "Y", "Z"]}

    else:
        tool_offsets = {"X": 0, "Y": 0, "Z": 0}

    adjusted_target_position = {
        key: target_position[key] + tool_offsets[key] for key in ["X", "Y", "Z"]
    }

    previous_position = None
    last_movement_time = time.time()

    while True:
        current_position_raw = client.read("$POS_ACT", debug=True).decode("utf-8")

        current_data = current_position_raw.replace("E6POS:", "").strip().split(",")
        current_position = parse_robot_data(current_data)
        print(current_data)

        # Collision check - this will raise ValueError if collision detected
        # is_in_collision_zone(current_position, client)

        # print(f"Position dictionary: {current_position}")

        if previous_position is not None:
            position_changed = any(
                current_position[key] != previous_position[key]
                for key in current_position.keys()
            )
            if position_changed:
                last_movement_time = time.time()

        # Update previous position
        previous_position = current_position.copy()

        # Compare only X, Y, and Z positions
        position_reached = all(
            abs(current_position[key] - adjusted_target_position[key]) <= tolerance
            for key in ["X", "Y", "Z"]
        )

        if position_reached:
            print("Target position reached (X, Y, Z). Ready for next movement.")
            break

        # Check if robot hasn't moved for the timeout duration
        if time.time() - last_movement_time > timeout:
            raise TimeoutError(
                f"Robot position hasn't changed for {timeout} seconds. Movement may be stuck."
            )

        time.sleep(0.1)


# Define preset locations
PLACE_POSITIONS = {
    "bin": {"X": 110.5, "Y": -1543, "Z": 1380, "A": 88, "B": 0, "C": 179.6},
    "Conveyor": {"X": 1500, "Y": -490, "Z": 1100, "A": 90, "B": 0, "C": 180},
}


def pick_and_place(
    client,
    pick_x,
    pick_y,
    pick_z,
    pick_coords_angle,
    tool_offset,
    location2place_coords,
    Move_type="PTP",
) -> None:
    """
    Execute a complete pick and place operation.

    Args:
        client: Robot client connection
        pick_x: X coordinate for picking
        pick_y: Y coordinate for picking
        pick_z: Z coordinate for picking
        pick_coords_angle: Rotation angle for picking
        tool_offset: Tool offset values
        location2place_coords: Coordinates for placing the item
        Move_type (str, optional): Specifies the movement type. Defaults to "PTP". Accepts either "PTP" or "LIN". Pass "LIN" if specified by the user.

    Raises:
        ValueError: If client is None or coordinates are invalid
        TimeoutError: If position is not reached within timeout
    """
    if client is None:
        raise ValueError("Robot client is not connected")

    if pick_x is None or pick_y is None:
        raise ValueError("Pick coordinates cannot be None")

    # Move above pick position
    cartesian_movement(
        client,
        pick_x,
        pick_y,
        1250,
        pick_coords_angle,
        0,
        180,
        Move_type=Move_type,
        tool_frame=tool_offset,
    )
    wait_for_target_position(
        client,
        target_position={
            "X": pick_x,
            "Y": pick_y,
            "Z": 1250,
        },
        # timeout=30,
        tolerance=0.5,
        tool_frame=tool_offset,
    )
    time.sleep(0.5)

    # Move down to pick Z
    cartesian_movement(
        client,
        pick_x,
        pick_y,
        pick_z,
        pick_coords_angle,
        0,
        180,
        Move_type=Move_type,
        tool_frame=tool_offset,
    )
    wait_for_target_position(
        client,
        target_position={
            "X": pick_x,
            "Y": pick_y,
            "Z": pick_z,
        },
        # timeout=30,
        tolerance=0.5,
        tool_frame=tool_offset,
    )
    time.sleep(0.5)

    # Close gripper
    control_gripper(client, "close")
    time.sleep(0.5)

    # Move up again
    cartesian_movement(
        client,
        pick_x,
        pick_y,
        1300,
        pick_coords_angle,
        0,
        180,
        Move_type=Move_type,
        tool_frame=tool_offset,
    )
    wait_for_target_position(
        client,
        target_position={
            "X": pick_x,
            "Y": pick_y,
            "Z": 1300,
        },
        # timeout=30,
        tolerance=0.5,
        tool_frame=tool_offset,
    )
    time.sleep(0.5)

    adjusted_z = location2place_coords["Z"] + 200

    # Now move to place position
    cartesian_movement(
        client,
        location2place_coords["X"],
        location2place_coords["Y"],
        adjusted_z,
        location2place_coords["A"],
        location2place_coords["B"],
        location2place_coords["C"],
        Move_type=Move_type,
    )
    wait_for_target_position(
        client,
        target_position={
            "X": location2place_coords["X"],
            "Y": location2place_coords["Y"],
            "Z": adjusted_z,
        },
        # timeout=30,
        tolerance=0.5,
    )
    time.sleep(0.5)

    # Lower to final place position
    cartesian_movement(
        client,
        location2place_coords["X"],
        location2place_coords["Y"],
        location2place_coords["Z"],
        location2place_coords["A"],
        location2place_coords["B"],
        location2place_coords["C"],
        Move_type=Move_type,
    )
    wait_for_target_position(
        client,
        target_position={
            "X": location2place_coords["X"],
            "Y": location2place_coords["Y"],
            "Z": location2place_coords["Z"],
        },
        # timeout=30,
        tolerance=0.5,
    )
    time.sleep(0.5)
    # Close gripper
    control_gripper(client, "close")
    time.sleep(0.5)
def normalize_angle(angle):
    """
    Normalize angle to be between -180 and 180 degrees.

    Args:
        angle (float): Angle in degrees

    Returns:
        float: Normalized angle between -180 and 180 degrees
    """
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


def joint_movement(
    client: openshowvar,
    a1: float = 0,
    a2: float = 0,
    a3: float = 0,
    a4: float = 0,
    a5: float = 0,
    a6: float = 0,
) -> None:
    """
    Send joint movement command to the robot.

    Args:
        client (openshowvar): Robot client object
        a1 (float): Relative movement for joint A1 in degrees
        a2 (float): Relative movement for joint A2 in degrees
        a3 (float): Relative movement for joint A3 in degrees
        a4 (float): Relative movement for joint A4 in degrees
        a5 (float): Relative movement for joint A5 in degrees
        a6 (float): Relative movement for joint A6 in degrees

    Returns:
        None
    """
    if client is None:
        raise ValueError("Robot client is not connected")

    # Get current joint positions
    current_axis_str = client.read("$AXIS_ACT", debug=True).decode("utf-8")
    current_axis_data = current_axis_str.strip("{}").replace("E6AXIS:", "").split(",")

    # Parse current joint positions
    current_joints = {}
    for item in current_axis_data:
        if len(item.split()) == 2:
            joint_name, joint_value = item.split()
            current_joints[joint_name] = float(joint_value)

    # Calculate new joint positions with relative movements
    new_a1 = normalize_angle(current_joints.get("A1", 0) + a1)
    new_a2 = normalize_angle(current_joints.get("A2", 0) + a2)
    new_a3 = normalize_angle(current_joints.get("A3", 0) + a3)
    new_a4 = normalize_angle(current_joints.get("A4", 0) + a4)
    new_a5 = normalize_angle(current_joints.get("A5", 0) + a5)
    new_a6 = normalize_angle(current_joints.get("A6", 0) + a6)

    # Format joint positions for robot command
    new_joints = f"{{A1 {new_a1:.3f}, A2 {new_a2:.3f}, A3 {new_a3:.3f}, A4 {new_a4:.3f}, A5 {new_a5:.3f}, A6 {new_a6:.3f}}}"

    # Send joint position command
    client.write(
        "COM_E6AXIS", new_joints, debug=True
    )  # Set target joint positions for CASE 2 movement

    # Set joint velocity and acceleration (if needed)
    client.write("$VEL.AXIS[1]", "50", debug=True)  # Set joint velocity percentage
    client.write("$ACC.AXIS[1]", "50", debug=True)  # Set joint acceleration percentage

    # Trigger CASE 2: Move Joints
    client.write("COM_ACTION", "2", debug=True)

    print(f"🚀 Moving joints to {new_joints}")


def parse_joint_data(axis_string):
    """Helper function to parse robot joint data into a dictionary"""
    axis_data = axis_string.strip("{}").replace("E6AXIS:", "").split(",")
    return {
        item.split()[0]: float(item.split()[1])
        for item in axis_data
        if len(item.split()) == 2
    }


def wait_for_target_joint_position(
    client: openshowvar,
    target_joints: dict,
    timeout: float = 10,
    tolerance: float = 0.5,
) -> None:
    """
    Wait until the robot's joint positions match the target positions within a given tolerance.

    Args:
        client (openshowvar): Robot client object
        target_joints (dict): Target joint positions with A1, A2, A3, A4, A5, A6
        timeout (float): Maximum time in seconds to wait without position change
        tolerance (float): Acceptable joint position error in degrees

    Returns:
        None
    """
    if client is None:
        raise ValueError("Robot client is not connected")

    if not all(key in target_joints for key in ["A1", "A2", "A3", "A4", "A5", "A6"]):
        raise ValueError("Target joints must contain A1, A2, A3, A4, A5, A6")

    previous_joints = None
    last_movement_time = time.time()

    while True:
        current_axis_str = client.read("$AXIS_ACT", debug=True).decode("utf-8")
        current_joints = parse_joint_data(current_axis_str)

        # Check if we're within tolerance for all joints
        within_tolerance = True
        for joint in ["A1", "A2", "A3", "A4", "A5", "A6"]:
            diff = abs(current_joints.get(joint, 0) - target_joints[joint])
            if diff > tolerance:
                within_tolerance = False
                break

        if within_tolerance:
            print("✅ Target joint position reached")
            break

        # Check if robot is still moving
        if previous_joints is not None:
            joints_changed = False
            for joint in ["A1", "A2", "A3", "A4", "A5", "A6"]:
                if (
                    abs(current_joints.get(joint, 0) - previous_joints.get(joint, 0))
                    > 0.01
                ):
                    joints_changed = True
                    break

            if joints_changed:
                last_movement_time = time.time()
            elif time.time() - last_movement_time > timeout:
                print("⚠️ Joint movement timeout - robot may have stopped")
                break

        previous_joints = current_joints.copy()
        time.sleep(0.1)
