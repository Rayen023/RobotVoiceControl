from dotenv import load_dotenv
from google import genai
from google.genai import types
import wave

load_dotenv()


# Set up the wave file to save the output:
def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
   with wave.open(filename, "wb") as wf:
      wf.setnchannels(channels)
      wf.setsampwidth(sample_width)
      wf.setframerate(rate)
      wf.writeframes(pcm)

client = genai.Client()
import pyaudio  
import wave  
p = pyaudio.PyAudio()  
# #open stream  
stream = p.open(format = p.get_format_from_width(2),  
                channels = 1,  
                rate = 24000,  
                output = True)  

#define stream chunk   
chunk = 1024  
  
#open a wav format music  
def speak_text(text: str) -> None:
    response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",
    contents=text,
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                voice_name='Kore',
                )
            )
        ),
    )
    )

    data = response.candidates[0].content.parts[0].inline_data.data
    stream.write(data)  

