import os
import wave

import pyaudio
from dotenv import load_dotenv
from google import genai

from src.agent_common import graph
from tts import speak_text

load_dotenv()

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME = "temp_recording.wav"

transcription_client = genai.Client()


def record_audio():
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
    )

    print("Listening... (Recording 5 seconds)")

    frames = []
    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(WAVE_OUTPUT_FILENAME, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    return WAVE_OUTPUT_FILENAME


def transcribe_audio(audio_file):
    try:
        with open(audio_file, "rb") as f:
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
        if os.path.exists(audio_file):
            os.remove(audio_file)


def main():
    print("Starting voice-controlled agent...")
    print("Press Ctrl+C to stop.")

    thread_id = "1"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        while True:
            print("\nListening for your voice...")
            audio_file = record_audio()

            transcription = transcribe_audio(audio_file)
            if not transcription:
                print("Failed to transcribe audio. Please try again.")
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
