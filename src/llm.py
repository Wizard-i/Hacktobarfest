"""
llm.py — Gemini API দিয়ে Gemma মডেল কল করে।
মাল্টি-টার্ন conversation history সাপোর্ট সহ।
মডেল বদলাতে চাইলে শুধু .env এ GEMMA_MODEL পরিবর্তন করুন।
"""

import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# ——— কনফিগ ———
_API_KEY   = os.getenv("GEMINI_API_KEY", "")
_MODEL_ID  = os.getenv("GEMMA_MODEL", "gemma-3-27b-it")

# ——— Gemini client (lazy-init) ———
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Lazy-init করে একটিমাত্র client instance রাখে।"""
    global _client
    if _client is None:
        if not _API_KEY:
            raise ValueError(
                "GEMINI_API_KEY সেট করা নেই। "
                ".env ফাইলে GEMINI_API_KEY=<your_key> যোগ করুন।"
            )
        _client = genai.Client(api_key=_API_KEY)
    return _client


def ask_gemma(system_prompt: str, user_message: str, history: list | None = None) -> str:
    """
    Gemma মডেলে একটি প্রশ্ন পাঠায় এবং উত্তর টেক্সট হিসেবে ফেরত দেয়।
    মাল্টি-টার্ন conversation history সাপোর্ট করে।

    Parameters
    ----------
    system_prompt : str
        নিয়মকানুন + বাস ডেটা সহ system instruction।
    user_message : str
        ব্যবহারকারীর বর্তমান প্রশ্ন।
    history : list | None
        Gradio chatbot type="messages" ফরম্যাটের আগের কথোপকথন।
        [{"role": "user"|"assistant", "content": "..."}, ...]

    Returns
    -------
    str
        মডেলের উত্তর।
    """
    if not _API_KEY:
        return (
            "⚠️ Gemini API key সেট করা নেই। .env ফাইলে GEMINI_API_KEY=<your_key> লিখে আবার চেষ্টা করুন।\n\n"
            "এই মুহূর্তে অ্যাপটি ডেটা প্রদর্শন ও রুট তথ্য দেখাতে প্রস্তুত, কিন্তু LLM উত্তর তৈরি করতে API প্রয়োজন।"
        )

    client = _get_client()

    # ——— conversation history → Gemini Content objects ———
    contents: list[types.Content] = []

    if history:
        for msg in history:
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            # Gemini API: "assistant" → "model"
            gemini_role = "model" if role == "assistant" else "user"
            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part(text=content)],
                )
            )

    # বর্তমান ব্যবহারকারীর প্রশ্ন যোগ করো
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=user_message)],
        )
    )

    response = client.models.generate_content(
        model=_MODEL_ID,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.3,        # কম temperature → নির্ভরযোগ্য তথ্য
            max_output_tokens=1024,
            top_p=0.9,
        ),
    )

    # উত্তর বের করা
    try:
        return response.text.strip()
    except (AttributeError, ValueError):
        return "দুঃখিত, মডেল থেকে উত্তর পাওয়া যায়নি। আবার চেষ্টা করুন।"


def get_model_info() -> dict:
    """বর্তমান মডেল ও API কনফিগ তথ্য রিটার্ন করে (ডিবাগিংয়ের জন্য)।"""
    return {
        "model_id":    _MODEL_ID,
        "api_key_set": bool(_API_KEY),
        "provider":    "Google AI Studio (Gemini API)",
    }
