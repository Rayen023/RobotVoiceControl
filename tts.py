import os

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

# Azure Speech Config
AZURE_SUBSCRIPTION_KEY = os.getenv("AZURE_SUBSCRIPTION_KEY")
AZURE_REGION = os.getenv("AZURE_REGION")


def speak_text(text: str) -> None:
    """
    Synthesize and speak the provided text using Azure Speech services.

    Args:
        text (str): The text to be spoken

    Returns:
        None
    """
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SUBSCRIPTION_KEY, region=AZURE_REGION
    )
    audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )
    result = synthesizer.speak_text_async(text).get()

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("[🔊 TTS] Speech synthesized.")
    else:
        print(f"[❌ TTS] Failed: {result.reason}")
