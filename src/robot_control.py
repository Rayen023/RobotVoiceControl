import asyncio
import csv
import io
import math
import time
from ftplib import FTP_TLS

import telnetlib3

# from py_openshowvar import openshowvar


# Mock openshowvar class for testing without actual robot connection
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


# === IP Configurations ===
COGNEX_IP = "192.169.2.99"
ROBOT_IP = "192.169.2.100"
ROBOT_PORT = 7000

# === FTP/Cognex Config
FTP_USER = "admin"
FTP_PASS = ""
FTP_CSV_FOLDER = "sdcard"
CSV_FILENAME = "DemoResults.csv"


# === Functions ===
async def trigger_camera(ip: str, user: str, password: str) -> None:
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
        reader, writer = await telnetlib3.open_connection(ip, 23)
        await asyncio.sleep(0.1)
        writer.write(user + "\r\n")
        await asyncio.sleep(0.1)
        writer.write("\r\n" if not password else password + "\r\n")
        await asyncio.sleep(0.1)
        writer.write("SE8\r\n")
        await asyncio.sleep(0.5)
        print("✅ Camera triggered successfully via Telnet.")
        writer.close()
    except Exception as e:
        error_msg = f"❌ Telnet trigger failed: {e}"
        print(error_msg)
        raise Exception(f"Camera trigger failed: {str(e)}")


def fetch_cognex_patterns() -> tuple[int, dict, dict]:
    """
    Fetch the latest event and pattern data from the Cognex camera via FTP and CSV file.

    Returns:
        tuple: Contains:
            - event (int): Event number from CSV
            - pattern1 (dict): First pattern with X, Y, Angle or None if not detected
            - pattern2 (dict): Second pattern with X, Y, Angle or None if not detected

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
        if len(last_row) < 7:
            error_msg = "⚠️ CSV format error."
            print(error_msg)
            raise ValueError(error_msg)
        event = int(last_row[0])
        pattern1 = (
            {
                "X": float(last_row[1]),
                "Y": float(last_row[2]),
                "Angle": float(last_row[3]),
            }
            if last_row[1] and last_row[2]
            else None
        )
        pattern2 = (
            {
                "X": float(last_row[4]),
                "Y": float(last_row[5]),
                "Angle": float(last_row[6]),
            }
            if last_row[4] and last_row[5]
            else None
        )
        print(f"✅ Event={event}, Pattern1={pattern1}, Pattern2={pattern2}")
        return event, pattern1, pattern2
    except ValueError as e:
        # Re-raise ValueError for specific CSV issues
        raise
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
    x: float = 0,
    y: float = 0,
    z: float = 0,
    a: float = 0,
    b: float = 0,
    c: float = 0,
    Move: str = None,
    tool_frame: dict = None,
) -> None:
    """
    Send cartesian movement command to the robot.

    Args:
        client (openshowvar): Robot client object
        x (float): X position coordinate
        y (float): Y position coordinate
        z (float): Z position coordinate
        a (float): A rotation angle
        b (float): B rotation angle
        c (float): C rotation angle
        Move (str): Movement type (e.g., "PTP", "LIN")
        tool_frame (dict): Tool frame offset values

    Returns:
        None
    """
    if client is None:
        raise ValueError("Robot client is not connected")

    tool_frame = tool_frame or {"X": 0, "Y": 0, "Z": 0, "A": 0, "B": 0, "C": 0}
    new_pos = f"{{X {x+tool_frame['X']:.3f}, Y {y+tool_frame['Y']:.3f}, Z {z+tool_frame['Z']:.3f}, A {a+tool_frame['A']:.3f}, B {b+tool_frame['B']:.3f}, C {c+tool_frame['C']:.3f}}}"
    client.write("COM_E6POS", new_pos, debug=True)
    client.write("$VEL.CP", "0.1", debug=True)
    client.write("$ACC.CP", "0.1", debug=True)
    client.write("$MOVE_CMD", Move, debug=True)
    client.write("COM_ACTION", "3", debug=True)
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
        client.write("COM_ACTION", "10", debug=True)  # CASE 10 to control output
        client.write("COM_VALUE1", "15", debug=True)  # OUT 15
        client.write("COM_VALUE2", "0", debug=True)  # Set OUT 15 to TRUE (gripper open)
        client.write("COM_ACTION", "10", debug=True)  # CASE 10 to control output
        client.write("COM_VALUE1", "16", debug=True)  # OUT 16
        client.write("COM_VALUE2", "0", debug=True)  # Set OUT 16 to FALSE
        print("Gripper is CLOSED.")

    elif state == "open":
        # Open the gripper (Set OUT 15 to TRUE and OUT 16 to TRUE)
        client.write("COM_ACTION", "10", debug=True)  # CASE 10 to control output
        client.write("COM_VALUE1", "15", debug=True)  # OUT 15
        client.write(
            "COM_VALUE2", "1", debug=True
        )  # Set OUT 15 to TRUE (gripper close)
        client.write("COM_ACTION", "10", debug=True)  # CASE 10 to control output
        client.write("COM_VALUE1", "16", debug=True)  # OUT 16
        client.write("COM_VALUE2", "0", debug=True)  # Set OUT 16 to TRUE
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


def wait_for_target_position(
    client: openshowvar,
    target_position: dict,
    timeout: float = 30,
    tolerance: float = 0.1,
    tool_frame: dict = None,
) -> None:
    """
    Wait until the robot's position matches the target position within a given tolerance.

    Args:
        client (openshowvar): Robot client object
        target_position (dict): Target position with X, Y, Z coordinates
        timeout (float): Maximum waiting time in seconds
        tolerance (float): Acceptable position error
        tool_frame (dict): Tool offset values

    Returns:
        None
    """
    if client is None:
        raise ValueError("Robot client is not connected")

    if not all(key in target_position for key in ["X", "Y", "Z"]):
        raise ValueError("Target position must contain X, Y, and Z coordinates")

    start_time = time.time()

    # Apply tool offset if provided
    if tool_frame:
        tool_offsets = {key: tool_frame.get(key, 0) for key in ["X", "Y", "Z"]}
    else:
        tool_offsets = {"X": 0, "Y": 0, "Z": 0}

    adjusted_target_position = {
        key: target_position[key] + tool_offsets[key] for key in ["X", "Y", "Z"]
    }
    while True:
        # Read the current position from the robot
        current_position_raw = client.read("$POS_ACT", debug=True).decode("utf-8")
        # Print raw data for debugging
        print(f"Current position: {current_position_raw}")
        current_data = current_position_raw.replace("E6POS:", "").strip().split(",")
        print(f"Current data: {current_data}")
        current_position = {}
        for item in current_data:
            if len(item.split()) == 2:
                key, value = item.split()
                current_position[key] = float(value)
        print(f"Position dictionary: {current_position}")

        # Compare only X, Y, and Z positions
        position_reached = all(
            abs(current_position[key] - adjusted_target_position[key]) <= tolerance
            for key in ["X", "Y", "Z"]
        )

        if position_reached:
            print("Target position reached (X, Y, Z). Ready for next movement.")
            break

        # Check for timeout
        if time.time() - start_time > timeout:
            raise TimeoutError(
                f"Timeout waiting for target position. Current: {current_position}, Target: {adjusted_target_position}"
            )
            break

        time.sleep(0.1)


# Define preset locations
PLACE_POSITIONS = {
    "blue bin": {"X": 500, "Y": 300, "Z": 1200, "A": 180, "B": 0, "C": 180},
    "Conveyor": {"X": 1500, "Y": -490, "Z": 1300, "A": 90, "B": 0, "C": 180},
}


def pick_and_place(
    client,
    pick_x,
    pick_y,
    pick_z,
    pick_coords_angle,
    tool_offset,
    location2place_coords,
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
        Move="PTP",
        tool_frame=tool_offset,
    )
    wait_for_target_position(
        client,
        target_position={
            "X": pick_x,
            "Y": pick_y,
            "Z": 1250,
        },
        timeout=30,
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
        Move="PTP",
        tool_frame=tool_offset,
    )
    wait_for_target_position(
        client,
        target_position={
            "X": pick_x,
            "Y": pick_y,
            "Z": pick_z,
        },
        timeout=30,
        tolerance=0.5,
        tool_frame=tool_offset,
    )
    time.sleep(0.5)

    # Close gripper
    control_gripper(client, "close")

    # Move up again
    cartesian_movement(
        client,
        pick_x,
        pick_y,
        1300,
        pick_coords_angle,
        0,
        180,
        Move="PTP",
        tool_frame=tool_offset,
    )
    wait_for_target_position(
        client,
        target_position={
            "X": pick_x,
            "Y": pick_y,
            "Z": 1300,
        },
        timeout=30,
        tolerance=0.5,
        tool_frame=tool_offset,
    )
    time.sleep(0.5)

    # Now move to place position
    cartesian_movement(
        client,
        location2place_coords["X"],
        location2place_coords["Y"],
        location2place_coords["Z"],
        location2place_coords["A"],
        location2place_coords["B"],
        location2place_coords["C"],
        Move="PTP",
    )
    wait_for_target_position(
        client,
        target_position={
            "X": location2place_coords["X"],
            "Y": location2place_coords["Y"],
            "Z": location2place_coords["Z"],
        },
        timeout=30,
        tolerance=0.5,
    )
    time.sleep(0.5)

    # Lower to final place position
    cartesian_movement(
        client,
        location2place_coords["X"],
        location2place_coords["Y"],
        1100,
        location2place_coords["A"],
        location2place_coords["B"],
        location2place_coords["C"],
        Move="PTP",
    )
    wait_for_target_position(
        client,
        target_position={
            "X": location2place_coords["X"],
            "Y": location2place_coords["Y"],
            "Z": 1100,
        },
        timeout=30,
        tolerance=0.5,
    )
    time.sleep(0.5)
