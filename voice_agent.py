import os
import time
import wave

import numpy as np
import pyaudio
import torch
from dotenv import load_dotenv
from google import genai
from silero_vad import (
    VADIterator,
    collect_chunks,
    get_speech_timestamps,
    load_silero_vad,
    read_audio,
    save_audio,
)

from src.agent_common import graph
from src.tts import speak_text

load_dotenv()

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 512
MAX_RECORD_SECONDS = 30  # Maximum recording time in seconds
SILENCE_THRESHOLD = (
    5.0  # How long to wait (in seconds) after last speech before stopping
)
SPEECH_TIMEOUT = 10  # Maximum time to wait for speech to start (in seconds)
WAVE_OUTPUT_FILENAME = "temp_recording.wav"
PROCESSED_AUDIO_FILENAME = "processed_recording.wav"

transcription_client = genai.Client()


USE_ONNX = True
vad_model = load_silero_vad(onnx=USE_ONNX)


def record_audio():
    """Record audio with dynamic VAD-based stopping when the user stops speaking"""
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
    )

    print(
        "Listening... (Speak now, will stop recording when you finish)"
    )  # Initialize with a much longer minimum silence duration (3000ms = 3 seconds)
    vad_iterator = VADIterator(
        model=vad_model,
        threshold=0.6,  # Slightly more sensitive to detect speech
        sampling_rate=RATE,
        min_silence_duration_ms=5000,  # Wait for 3 seconds of silence before ending speech
        speech_pad_ms=500,  # Add 500ms padding to speech segments
    )

    frames = []
    is_speech_started = False
    last_speech_time = time.time()
    start_time = time.time()

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            audio_chunk = (
                np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            )

            vad_result = vad_iterator(audio_chunk)

            current_time = time.time()
            elapsed_time = current_time - start_time

            # Check if we received a speech start timestamp
            if vad_result is not None and "start" in vad_result:
                is_speech_started = True
                last_speech_time = (
                    current_time  # Check if we received a speech end timestamp
                )
            if vad_result is not None and "end" in vad_result:
                if is_speech_started:
                    # Instead of stopping right away, give some extra time for another sentence
                    print("Speech pause detected, continuing to listen for more...")
                    # Update last_speech_time to give more buffer time
                    last_speech_time = current_time

            # Hard stop after maximum recording time
            if elapsed_time > MAX_RECORD_SECONDS:
                print("Maximum recording time reached")
                break

            # Only stop after significant silence following speech detection
            if is_speech_started and (
                current_time - last_speech_time > SILENCE_THRESHOLD
            ):
                print("Extended silence detected, stopping recording")
                break

            if not is_speech_started and (elapsed_time > SPEECH_TIMEOUT):
                print("No speech detected, stopping recording")
                break

    finally:
        vad_iterator.reset_states()
        stream.stop_stream()
        stream.close()
        audio.terminate()

    if not frames or not is_speech_started:
        print("No speech detected in recording")
        return None

    with wave.open(WAVE_OUTPUT_FILENAME, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    return WAVE_OUTPUT_FILENAME


def process_audio_with_vad(audio_file):
    """Process audio with Silero VAD to extract speech segments"""
    try:
        wav = read_audio(audio_file, sampling_rate=RATE)

        speech_timestamps = get_speech_timestamps(
            wav,
            vad_model,
            sampling_rate=RATE,
            threshold=0.45,  # Slightly lower threshold to be more sensitive to speech
            min_silence_duration_ms=1000,  # Allow 1 second pauses within speech
            speech_pad_ms=500,  # Add padding around speech segments
        )

        if not speech_timestamps:
            print("No speech detected in the recording")
            return None

        total_speech_duration = (
            sum((chunk["end"] - chunk["start"]) for chunk in speech_timestamps) / RATE
        )

        if total_speech_duration < 1.0:
            print(
                f"Speech detected is too short ({total_speech_duration:.2f} seconds), ignoring"
            )
            return None

        # Merge all speech chunks to one audio
        save_audio(
            PROCESSED_AUDIO_FILENAME,
            collect_chunks(speech_timestamps, wav),
            sampling_rate=RATE,
        )

        return PROCESSED_AUDIO_FILENAME
    except Exception as e:
        print(f"Error processing audio with VAD: {e}")
        return None


def transcribe_audio(audio_file):
    try:
        # Process audio with VAD first
        processed_file = process_audio_with_vad(audio_file)

        if not processed_file:
            return None

        with open(processed_file, "rb") as f:
            audio_bytes = f.read()

        response = transcription_client.models.generate_content(
            model="gemini-2.5-flash-preview-04-17",
            contents=[
                """Transcribe this audio. You are a transcription assistant in the context of a voice controlled robot that follows commands.
                Some examples of commands are: "move to position A","move 20 centimeters to the right", "pick up the object a box or some wood or ...", "What max weight it can handle"., etc.
                Your task is to transcribe the audio and return the text without any additional information.
                The audio can be in English or French.
                """,
                genai.types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type="audio/wav",
                ),
            ],
        )

        return response.text
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return None
    finally:
        # Clean up the temporary files
        if os.path.exists(audio_file):
            os.remove(audio_file)
        if os.path.exists(PROCESSED_AUDIO_FILENAME):
            os.remove(PROCESSED_AUDIO_FILENAME)


def main():
    print("Starting voice-controlled agent with Silero VAD integration...")
    print("Press Ctrl+C to stop.")

    thread_id = "1"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        while True:
            print("\nListening for your voice...")
            audio_file = record_audio()

            if not audio_file:
                print("No valid audio recorded. Please try again.")
                continue

            transcription = transcribe_audio(audio_file)
            if not transcription:
                print(
                    "Failed to transcribe audio or no significant speech detected. Please try again."
                )
                continue

            print(f"You said: {transcription}")

            events = graph.stream(
                {"messages": [{"role": "user", "content": transcription}]},
                config,
                stream_mode="values",
            )

            final_response = ""
            for event in events:
                final_response = event["messages"][-1].content

            print("\nAI Assistant:", final_response)
            speak_text(final_response)
    except KeyboardInterrupt:
        print("\nExiting voice-controlled agent. Goodbye!")


if __name__ == "__main__":
    main()
