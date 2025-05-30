import asyncio
import base64
import logging
import os
from typing import List, Optional

import cv2
import numpy as np
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from src.tts import speak_text

logger = logging.getLogger(__name__)
load_dotenv()

# Lazy import for DeepFace
DeepFace = None


def get_deepface():
    global DeepFace
    if DeepFace is None:
        speak_text("Chargement des modules de vision, cela prend quelques secondes.")
        from deepface import DeepFace as DF

        DeepFace = DF
    return DeepFace


class FaceAnalysisResult:
    def __init__(self, face_id, bounding_box, dominant_emotion, emotion_confidence):
        self.face_id = face_id
        self.bounding_box = bounding_box
        self.dominant_emotion = dominant_emotion
        self.emotion_confidence = emotion_confidence


def capture_camera_image() -> Optional[np.ndarray]:
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        logger.error("Could not open camera")
        return None
    try:
        max_attempts = 10
        for _ in range(max_attempts):
            ret, frame = camera.read()
            if not ret:
                logger.error("Could not capture image from camera")
                return None
            if np.any(frame > 10):
                logger.info("Successfully captured camera image")
                return frame
            import time

            time.sleep(0.5)
        logger.warning("All captured images were too dark")
        return None
    finally:
        camera.release()


async def analyze_faces(image_np: np.ndarray) -> List[FaceAnalysisResult]:
    faces_data = []
    try:
        DF = get_deepface()
        results = await asyncio.to_thread(
            DF.analyze,
            img_path=image_np,
            actions=["emotion"],
            detector_backend="yolov11m",
            align=True,
            enforce_detection=True,
        )
        if isinstance(results, list):
            for i, face_info in enumerate(results):
                region = face_info.get("region")
                if not region:
                    continue
                emotions = face_info.get("emotion", {})
                dominant_emotion = face_info.get("dominant_emotion", "unknown")
                emotion_confidence = max(emotions.values()) if emotions else 0.0
                faces_data.append(
                    FaceAnalysisResult(
                        face_id=i + 1,
                        bounding_box={
                            "x": region["x"],
                            "y": region["y"],
                            "width": region["w"],
                            "height": region["h"],
                        },
                        dominant_emotion=dominant_emotion,
                        emotion_confidence=emotion_confidence,
                    )
                )
    except Exception as e:
        logger.warning(f"DeepFace analysis failed: {e}")
    return faces_data


llm = ChatOpenAI(
    openai_api_key=os.environ["OPENROUTER_API_KEY"],
    openai_api_base=os.environ["OPENROUTER_BASE_URL"],
    model_name="google/gemini-2.5-flash-preview-05-20",
    temperature=0,
    max_tokens=8096,
    timeout=None,
    max_retries=2,
    streaming=True,
)


async def generate_image_description(image_np: np.ndarray) -> str:
    try:
        _, buffer = cv2.imencode(".jpg", image_np)
        image_data = base64.b64encode(buffer).decode("utf-8")
        message = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Generate in a single sentence a description of the image in french. If a human is included in the image it is the robot's operator so call him as such",
                },
                {
                    "type": "image",
                    "source_type": "base64",
                    "data": image_data,
                    "mime_type": "image/jpeg",
                },
            ],
        }
        result = await llm.ainvoke([message])
        return result.content
    except Exception as e:
        logger.error(f"Error generating image description: {e}")
        return "Erreur lors de la génération de la description"


async def process_image_with_services(image_np: np.ndarray) -> dict:
    result = {"faces": [], "image_description": None, "errors": []}
    try:
        faces = await analyze_faces(image_np)
        result["faces"] = [
            {
                "face_id": face.face_id,
                "dominant_emotion": face.dominant_emotion,
                "emotion_confidence": face.emotion_confidence,
                "bounding_box": face.bounding_box,
            }
            for face in faces
        ]
    except Exception as e:
        result["errors"].append(f"Face analysis failed: {str(e)}")
    try:
        description = await generate_image_description(image_np)
        result["image_description"] = description
    except Exception as e:
        result["errors"].append(f"Image description failed: {str(e)}")
    return result


def format_analysis_output(result: dict) -> str:
    output_parts = []
    if result["errors"]:
        output_parts.append("Errors occurred during analysis:")
        for error in result["errors"]:
            output_parts.append(f"- {error}")
        output_parts.append("")
    if result["image_description"]:
        output_parts.append(f"Description: {result['image_description']}")
    else:
        output_parts.append("No image description available.")
    faces = result["faces"]
    if faces:
        output_parts.append(f"\nFaces detected: {len(faces)}")
        for face in faces:
            emotion = face["dominant_emotion"]
            confidence = face["emotion_confidence"]
            output_parts.append(
                f"Face {face['face_id']}: {emotion} (confidence: {confidence:.2f})"
            )
    else:
        output_parts.append("\nNo faces detected in the image.")
    return "\n".join(output_parts)


@tool
def get_emotion_and_description() -> str:
    """
    Analyze the environment by capturing an image from the camera, processes it, and returns a string
    containing either an error message or the image description plus emotion information of the robot's operator present in the image.

    Returns:
        A string with either an error message or image description with emotion data.
    """
    try:
        image_np = capture_camera_image()
        if image_np is None:
            return "Error: Could not capture image from camera."
        try:
            cv2.imwrite("captured_image.png", image_np)
            logger.info("Captured image saved to captured_image.png")
        except Exception as e:
            logger.warning(f"Could not save captured image: {e}")
        result = asyncio.run(process_image_with_services(image_np))
        # If no faces and no description, make sure to return a clear message
        if not result["faces"] and not result["image_description"]:
            return "No faces detected and no image description available."
        print("Result:", result)
        print("Formatted Output:", format_analysis_output(result))
        print("Output:", format_analysis_output(result))
        return format_analysis_output(result)
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return f"Error processing image: {str(e)}"
