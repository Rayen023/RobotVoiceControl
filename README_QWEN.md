# Qwen2-Audio Voice Agent

This is a voice agent implementation that uses Qwen2-Audio-7B-Instruct for audio transcription and understanding. 
It provides a voice interface for robot control commands through audio analysis and natural language processing.

## Requirements

- Python 3.8 or above
- PyTorch
- Transformers (install the latest version from GitHub)
- Librosa
- Silero VAD
- PyAudio

## Installation

1. Make sure you have all dependencies installed:
   ```
   pip install torch librosa pyaudio
   pip install git+https://github.com/huggingface/transformers
   ```

2. The script will automatically download the Qwen2-Audio-7B-Instruct model on first run.
   Note that the model is ~7GB, so make sure you have enough disk space and a good internet connection.

## Usage

Run the script with:
```
python voice_agent_qwen.py
```

The script will:
1. Load the Qwen2-Audio model (downloading it if necessary)
2. Listen for your voice input
3. Process the audio using Silero VAD (Voice Activity Detection)
4. Transcribe the audio using Qwen2-Audio
5. Process the transcription through the agent
6. Speak the response back to you

## Features

- Voice Activity Detection (VAD) for better audio capture
- Automatic speech detection and recording
- Silence detection for natural conversation flow
- Robot command context awareness
- Text-to-speech response

## Differences from the Gemini version

This agent uses Hugging Face's Qwen2-Audio-7B-Instruct model for audio transcription and understanding, 
rather than the Gemini API. This allows for:

- Local processing without internet dependency after model download
- No API costs or rate limits
- Audio understanding context directly in the model

The model is trained to understand speech and audio content, making it effective for voice command applications.

## Notes

- First-time initialization may take a few minutes to download and load the model.
- The model requires approximately 14GB of GPU memory for optimal performance.
- You can adjust voice detection sensitivity in the script parameters.
