from __future__ import annotations
from typing import List, Tuple
import pathlib
from fibz_bot.config import settings

try:
    from google.cloud import speech_v2 as speech
except Exception:
    speech = None

def transcribe_audio(path: str, language_code: str | None = None) -> str:
    language_code = language_code or settings.SPEECH_LANGUAGE
    if speech is None:
        return "(Transcription unavailable: google-cloud-speech not installed/initialized.)"
    client = speech.SpeechClient()
    with open(path, "rb") as f:
        audio_content = f.read()
    config = speech.RecognitionConfig(
        auto_decoding_config=speech.AutoDetectDecodingConfig(),
        language_codes=[language_code],
        model="long",
    )
    request = speech.RecognizeRequest(
        recognizer=f"projects/{settings.VERTEX_PROJECT_ID}/locations/{settings.VERTEX_LOCATION}/recognizers/_",
        config=config,
        content=audio_content,
    )
    response = client.recognize(request=request)
    lines = []
    for result in response.results:
        lines.append(result.alternatives[0].transcript)
    return "\n".join(lines)

def parse_audio(path: str):
    p = pathlib.Path(path)
    text = transcribe_audio(str(p))
    return [(text, {"modality":"audio","filename":p.name})]
