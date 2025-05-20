from typing import Any, Dict

import cv2
import numpy as np
from deepface import DeepFace
from dotenv import load_dotenv
from google import genai
from google.genai.types import Part
from langchain_core.tools import tool

load_dotenv()

def process_image(image_np: np.ndarray) -> Dict[str, Any]:
    """
    Process a single image frame with DeepFace and Gemini.

    Args:
        image_np: Numpy array containing the image

    Returns:
        Dictionary containing emotion analysis and image description
    """
    result = {"face_analysis": [], "image_description_fr": None}

    # Get image description using Gemini
    try:
        gemini_client = genai.Client()
        _, buffer = cv2.imencode(".jpg", image_np)
        image_bytes_for_gemini = buffer.tobytes()

        gemini_response = gemini_client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=[
                "Generate in a single sentence a description of the image in french.",
                Part.from_bytes(data=image_bytes_for_gemini, mime_type="image/jpeg"),
            ],
        )

        if (
            gemini_response
            and hasattr(gemini_response, "text")
            and gemini_response.text
        ):
            result["image_description_fr"] = gemini_response.text.strip()
    except Exception as e:
        result["image_description_error"] = str(e)

    # Process with DeepFace
    try:
        analysis_results = DeepFace.analyze(
            img_path=image_np,
            actions=["emotion"],
            detector_backend="yolov11m",
            align=True,
            enforce_detection=False,
        )

        faces_data = []
        if isinstance(analysis_results, list):
            for i, face_info in enumerate(analysis_results):
                region = face_info.get("region")
                if not region:
                    continue

                emotions = face_info.get("emotion", {})
                dominant_emotion = face_info.get("dominant_emotion", "unknown")
                emotion_confidence = (
                    max(emotions.values() or [0.0]) if emotions else 0.0
                )

                faces_data.append(
                    {
                        "face_id": i + 1,
                        "dominant_emotion": dominant_emotion,
                        "emotion_confidence": emotion_confidence,
                    }
                )

        result["face_analysis"] = faces_data
        result["total_faces"] = len(faces_data)
    except Exception as e:
        result["face_analysis_error"] = str(e)

    return result


@tool
def get_emotion_and_description() -> str:
    """
    Captures an image from the camera, processes it, and returns a string
    containing either an error message or the image description plus emotion information.

    Returns:
        A string with either an error message or image description with emotion data

    """

    # max_cameras = 10
    # available = [
    # ]

    # for i in range(max_cameras):
    #     cap = cv2.VideoCapture(i,cv2.CAP_DSHOW)
    #     if not cap.read()[0]:
    #         print(f"camera {i} not found")
    #         continue
    #     available.append(i)
    #     cap.release()
    
    # print(available)
    camera = cv2.VideoCapture(0)  # Use 0 for default camera

    if not camera.isOpened():
        return "Error: Could not open camera."

    while True:
        ret, frame = camera.read()
        if not ret:
            camera.release()
            return "Error: Could not capture image."

        # Check if the image is mostly black
        if np.any(frame > 10):  # Adjust the threshold if needed
            break  # Exit the loop once a non-black image is captured

        import time
        time.sleep(1)  # Adjust sleep time as needed

    camera.release()


    try:
        # Process the captured frame
        result = process_image(frame)

        # Check for errors
        if "face_analysis_error" in result:
            return f"Error in face analysis: {result['face_analysis_error']}"
        if "image_description_error" in result:
            return f"Error generating image description: {result['image_description_error']}"

        # Format the output string
        output = ""

        # Add image description if available
        if result["image_description_fr"]:
            output += f"Description: {result['image_description_fr']}\n"
        else:
            output += "No image description available.\n"

        # Add information about detected faces
        if result["total_faces"] > 0:
            for face in result["face_analysis"]:
                emotion = face["dominant_emotion"]
                confidence = face["emotion_confidence"]
                output += f"Face {face['face_id']}: {emotion} (confidence: {confidence:.2f})\n"
        else:
            output += "No faces detected in the image."

        return output.strip()

    except Exception as e:
        return f"Error processing image: {str(e)}"
#get_emotion_and_description()