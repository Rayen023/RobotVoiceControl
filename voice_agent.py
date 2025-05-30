import os
import re
import time
import uuid
import wave

import numpy as np
import pyaudio
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
#from src.tts_gemini import speak_text

thread_id = str(uuid.uuid4())  # Generate a unique thread ID for each session

load_dotenv()

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 512
WAVE_OUTPUT_FILENAME = "temp_recording.wav"
PROCESSED_AUDIO_FILENAME = "processed_recording.wav"

VAD_THRESHOLD = 0.65  # 0.6
VAD_MIN_SILENCE_DURATION_MS = 3000  # 5000
VAD_SPEECH_PAD_MS = 500  # 500

SPEECH_TIMESTAMP_THRESHOLD = 0.55  # 0.45
SPEECH_TIMESTAMP_MIN_SILENCE_DURATION_MS = 500  # 1500
SPEECH_TIMESTAMP_SPEECH_PAD_MS = 200  # 500

SPEECH_MIN_DURATION_SECONDS = 0.8  # 1.0

AUDIO_INT16_NORMALIZATION = 32768.0

transcription_client = genai.Client()


USE_ONNX = False
vad_model = load_silero_vad(onnx=USE_ONNX)


def record_audio():
    """Record audio with VAD-based detection of speech start and end"""
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
    )

    print("Listening... Speak now. Recording will stop on VAD 'end'.")
    vad_iterator = VADIterator(
        model=vad_model,
        threshold=VAD_THRESHOLD,
        sampling_rate=RATE,
        min_silence_duration_ms=VAD_MIN_SILENCE_DURATION_MS,
        speech_pad_ms=VAD_SPEECH_PAD_MS,
    )

    frames = []
    is_speech_started = False

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            audio_chunk = (
                np.frombuffer(data, dtype=np.int16).astype(np.float32)
                / AUDIO_INT16_NORMALIZATION
            )
            vad_result = vad_iterator(audio_chunk)

            # start detection
            if vad_result and "start" in vad_result:
                is_speech_started = True

            # immediate stop when VAD signals end-of-speech
            if vad_result and "end" in vad_result and is_speech_started:
                print("VAD end detected, stopping recording.")
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
            threshold=SPEECH_TIMESTAMP_THRESHOLD,
            min_silence_duration_ms=SPEECH_TIMESTAMP_MIN_SILENCE_DURATION_MS,
            speech_pad_ms=SPEECH_TIMESTAMP_SPEECH_PAD_MS,
        )

        if not speech_timestamps:
            print("No speech detected in the recording")
            return None

        total_speech_duration = (
            sum((chunk["end"] - chunk["start"]) for chunk in speech_timestamps) / RATE
        )

        if total_speech_duration < SPEECH_MIN_DURATION_SECONDS:
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

        start_transcription = time.time()
        print("Transcribing audio...")

        response = transcription_client.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",  # google/gemini-2.5-flash-preview-05-20
            contents=[
                """
                You are a transcription assistant specialized in voice-controlled KUKA robot. Transcribe the audio using the robotics context to resolve unclear words.
                Use your understanding of common robot commands (e.g., move axes, pick up, place, set home position, box, bin, conveyor, wood, orange box, centimeters) to correct homophones and noisy input.
                If uncertain about a term, provide your best guess in square brackets, e.g., [likely word].
                The audio may be in English or French. Return only the clean transcription text without extra commentary.
                """,
                genai.types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type="audio/wav",
                ),
            ],
        )
        end_transcription = time.time()
        print(
            f"Transcription completed in {end_transcription - start_transcription:.2f} seconds"
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


def clean_text_for_tts(text):
    """Clean text for text-to-speech by removing markdown and special characters"""
    if not text:
        return ""

    # Remove bullet points and list formatting
    text = re.sub(
        r"^\s*[\*\-\+]\s*", "", text, flags=re.MULTILINE
    )  # Remove bullet points
    text = re.sub(
        r"^\s*\d+\.\s*", "", text, flags=re.MULTILINE
    )  # Remove numbered lists

    # Remove markdown formatting (more specific patterns)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # Remove bold **text**
    text = re.sub(
        r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text
    )  # Remove italic *text* but not bullet points
    text = re.sub(r"`(.+?)`", r"\1", text)  # Remove code `text`
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)  # Remove code blocks

    # Remove other special characters that interfere with TTS
    text = re.sub(r"[#]+\s*", "", text)  # Remove headers ###
    text = re.sub(r"[\[\](){}]", "", text)  # Remove brackets
    text = re.sub(r"[_~^]", "", text)  # Remove underscores, tildes, carets
    text = re.sub(r"[-]{2,}", "", text)  # Remove multiple dashes

    # Clean up whitespace
    text = re.sub(r"\n+", " ", text)  # Replace newlines with spaces
    text = re.sub(r"\s+", " ", text)  # Replace multiple spaces with single space
    text = text.strip()  # Remove leading/trailing whitespace

    return text


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
            # Clean up the response text for TTS
            cleaned_response = clean_text_for_tts(final_response)
            speak_text(cleaned_response)
    except KeyboardInterrupt:
        print("\nExiting voice-controlled agent. Goodbye!")


if __name__ == "__main__":
    main()
