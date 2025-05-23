import os
import time
import uuid
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

thread_id = str(uuid.uuid4())  # Generate a unique thread ID for each session

load_dotenv()

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 512
MAX_RECORD_SECONDS = 30
SILENCE_THRESHOLD = 4.0
SPEECH_TIMEOUT = 10
WAVE_OUTPUT_FILENAME = "temp_recording.wav"
PROCESSED_AUDIO_FILENAME = "processed_recording.wav"

transcription_client = genai.Client()


USE_ONNX = False
vad_model = load_silero_vad(onnx=USE_ONNX)


def record_audio():
    """Record audio with dynamic VAD-based stopping when the user stops speaking"""
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
    )

    print("Listening... (Speak now, will stop recording when you finish)")
    vad_iterator = VADIterator(
        model=vad_model,
        threshold=0.6,
        sampling_rate=RATE,
        min_silence_duration_ms=5000,
        speech_pad_ms=500,
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

            if vad_result is not None and "start" in vad_result:
                is_speech_started = True
                last_speech_time = current_time
            if vad_result is not None and "end" in vad_result:
                if is_speech_started:

                    print("Speech pause detected, continuing to listen for more...")

                    last_speech_time = current_time

            if elapsed_time > MAX_RECORD_SECONDS:
                print("Maximum recording time reached")
                break

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
            threshold=0.45,
            min_silence_duration_ms=1500,
            speech_pad_ms=500,
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

        processed_file = process_audio_with_vad(audio_file)

        if not processed_file:
            return None

        with open(processed_file, "rb") as f:
            audio_bytes = f.read()

        response = transcription_client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",  # google/gemini-2.5-flash-preview-05-20
            contents=[
                """
                You are a transcription assistant specialized in voice-controlled KUKA robot. Transcribe the audio using the robotics context to resolve unclear words.
                Use your understanding of common robot commands (e.g., move axes, pick up, place, set home position, box, bin, convayor, wood, centimeters) to correct homophones and noisy input.
                If uncertain about a term, provide your best guess in square brackets, e.g., [likely word].
                The audio may be in English or French. Return only the clean transcription text without extra commentary.
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

        if os.path.exists(audio_file):
            os.remove(audio_file)
        if os.path.exists(PROCESSED_AUDIO_FILENAME):
            os.remove(PROCESSED_AUDIO_FILENAME)


def main():
    print("Starting voice-controlled agent with Silero VAD integration...")
    print("Press Ctrl+C to stop.")

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

            print("\n" + "=" * 50)
            print(f"You said: {transcription}")
            print("=" * 50 + "\n")

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
