import pyaudio
import wave
from typing import List, Union
import io
from openai import OpenAI

# Parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
WAVE_OUTPUT_FILENAME = "output.wav"

def record_audio(duration: int, filename: str) -> None:
    """
    Record audio for specified duration and save to file.
    
    Args:
        duration (int): Recording duration in seconds
        filename (str): Output WAV filename
    """
    audio = pyaudio.PyAudio()
    print(f"Starting {duration} second recording...")
    
    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    
    frames = []
    for _ in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)
    
    print("Recording complete. Saving file...")
    stream.stop_stream()
    stream.close()
    
    # Save the recording
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
    
    audio.terminate()
    print(f"Saved to {filename}")

def save_audio(frames: List[bytes], filename: str) -> None:
    """
    Save recorded audio frames to a WAV file.
    
    Args:
        frames (List[bytes]): List of recorded audio frames
        filename (str): Output filename
    """
    audio = pyaudio.PyAudio()
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
    audio.terminate()

def play_audio(audio_input: Union[str, List[bytes]]) -> None:
    """
    Play audio from either a WAV file or recorded frames.
    
    Args:
        audio_input: Either a filename (str) or recorded frames (List[bytes])
    """
    audio = pyaudio.PyAudio()
    print("Playing back...")
    
    if isinstance(audio_input, str):
        # Play from file
        with wave.open(audio_input, 'rb') as wf:
            play_stream = audio.open(
                format=audio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            
            data = wf.readframes(CHUNK)
            while data:
                play_stream.write(data)
                data = wf.readframes(CHUNK)
    else:
        # Play from frames
        play_stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True
        )
        
        # Create an in-memory WAV file
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(audio.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(audio_input))
            
            # Reset buffer position and read
            wav_buffer.seek(0)
            with wave.open(wav_buffer, 'rb') as wf:
                data = wf.readframes(CHUNK)
                while data:
                    play_stream.write(data)
                    data = wf.readframes(CHUNK)
    
    play_stream.stop_stream()
    play_stream.close()
    audio.terminate()
    print("Playback complete.")

def transcribe_audio(filename: str) -> str:
    """
    Transcribe audio file using OpenAI's API.
    
    Args:
        filename (str): Path to the WAV file to transcribe
    
    Returns:
        str: Transcribed text
    """
    client = OpenAI()
    
    with open(filename, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    
    return transcription.text