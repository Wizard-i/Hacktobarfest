"""
stt.py — Whisper ব্যবহার করে মাইক্রোফোন বা অডিও ফাইল থেকে টেক্সট বের করে।
Bangla accuracy বাড়াতে .env এ WHISPER_SIZE=medium বা large-v3 ব্যবহার করুন।
"""

import os
import tempfile
import warnings
from pathlib import Path

import numpy as np
import whisper
from dotenv import load_dotenv

load_dotenv()

# ——— কনফিগ ———
# tiny | base | small | medium | large | large-v2 | large-v3
_WHISPER_SIZE = os.getenv("WHISPER_SIZE", "small")
_LANGUAGE     = os.getenv("WHISPER_LANGUAGE", "bn")  # bn = বাংলা

# ——— Model cache ———
_model: whisper.Whisper | None = None


def _get_model() -> whisper.Whisper:
    """Lazy-load করে Whisper মডেল ক্যাশ করে।"""
    global _model
    if _model is None:
        print(f"[STT] Whisper '{_WHISPER_SIZE}' মডেল লোড হচ্ছে...")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _model = whisper.load_model(_WHISPER_SIZE)
        print(f"[STT] মডেল লোড সম্পন্ন।")
    return _model


def transcribe_audio(audio_input) -> str:
    """
    অডিও ইনপুট থেকে টেক্সট বের করে।

    Parameters
    ----------
    audio_input : tuple | str | Path | np.ndarray
        Gradio থেকে আসা (sample_rate, numpy_array) টাপল,
        অথবা অডিও ফাইলের পাথ,
        অথবা numpy array।

    Returns
    -------
    str
        ট্রান্সক্রাইব করা টেক্সট। ব্যর্থ হলে খালি স্ট্রিং।
    """
    if audio_input is None:
        return ""

    model = _get_model()

    # ——— Gradio (sample_rate, array) টাপল হ্যান্ডল ———
    if isinstance(audio_input, tuple):
        sample_rate, audio_array = audio_input

        # float32 নিশ্চিত করা
        if audio_array.dtype != np.float32:
            audio_array = audio_array.astype(np.float32)
            if np.max(np.abs(audio_array)) > 1.0:
                audio_array /= 32768.0  # int16 → float32 normalize

        # স্টেরিও হলে মনো করা
        if audio_array.ndim == 2:
            audio_array = audio_array.mean(axis=1)

        # whisper সরাসরি numpy array নিতে পারে (16kHz আশা করে)
        result = model.transcribe(
            audio_array,
            language=_LANGUAGE,
            fp16=False,
        )

    # ——— ফাইল পাথ হ্যান্ডল ———
    elif isinstance(audio_input, (str, Path)):
        result = model.transcribe(
            str(audio_input),
            language=_LANGUAGE,
            fp16=False,
        )

    else:
        return "[অডিও ফরম্যাট সমর্থিত নয়]"

    text = result.get("text", "").strip()
    print(f"[STT] ট্রান্সক্রিপশন: {text!r}")
    return text


def get_whisper_info() -> dict:
    """বর্তমান Whisper কনফিগ তথ্য রিটার্ন করে।"""
    return {
        "model_size": _WHISPER_SIZE,
        "language":   _LANGUAGE,
        "loaded":     _model is not None,
    }
