"""
app.py — কুমিরা বাস বন্ধু: Gradio ইন্টারফেস
মাইক্রোফোন বা টেক্সটে প্রশ্ন করুন, Gemma উত্তর দেবে।
তিনটি ট্যাব: চ্যাট, বাস শিডিউল, রুট এক্সপ্লোরার
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import gradio as gr
import pytz
from dotenv import load_dotenv

# src/ ফোল্ডার পাথে যোগ করা
sys.path.insert(0, str(Path(__file__).parent / "src"))

from llm import ask_gemma, get_model_info
from prompts import (
    build_system_prompt,
    build_user_message,
    find_next_buses,
    get_current_time_info,
    load_bus_data,
)
from stt import get_whisper_info, transcribe_audio

load_dotenv()

# ——— অ্যাপ মেটাডেটা ———
APP_TITLE   = "🚌 কুমিরা বাস বন্ধু"
APP_VERSION = "2.0.0"
BD_TZ       = pytz.timezone("Asia/Dhaka")


# ════════════════════════════════════════════════
#  থিম
# ════════════════════════════════════════════════

custom_theme = gr.themes.Soft(
    primary_hue="green",
    secondary_hue="emerald",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Hind Siliguri"), "sans-serif"],
)


# ════════════════════════════════════════════════
#  কোর চ্যাট ফাংশন
# ════════════════════════════════════════════════

def process_voice(audio_input):
    """মাইক্রোফোনের অডিও → STT → প্রশ্ন বক্সে বসিয়ে দেয়।"""
    if audio_input is None:
        return "", gr.update()
    text = transcribe_audio(audio_input)
    if not text:
        return "", gr.update(value="⚠️ কথা বুঝতে পারিনি, আবার বলুন।")
    return text, gr.update()


def ask_question(user_text: str, history: list):
    """প্রশ্ন নেয় → system prompt + user message তৈরি → LLM কল → উত্তর।"""
    if not user_text or not user_text.strip():
        return history, ""

    user_msg = build_user_message(user_text)
    system_p = build_system_prompt()

    # conversation history পাস করো (multi-turn)
    answer = ask_gemma(system_p, user_msg, history=history)

    # চ্যাট ইতিহাসে যোগ
    history = history or []
    history.append({"role": "user",      "content": user_msg})
    history.append({"role": "assistant", "content": answer})

    return history, ""


def ask_next_bus(history: list):
    """'পরের বাস' বাটন — সরাসরি পরের বাস জিজ্ঞেস করে।"""
    time_info = get_current_time_info()
    question  = f"এখন {time_info['time_str']} বাজে ({time_info['day_bn']}), পরের বাসগুলো কখন কোথায় যাবে?"
    return ask_question(question, history)


def clear_chat():
    """চ্যাট ও ইনপুট বক্স পরিষ্কার করে।"""
    return [], ""


# ════════════════════════════════════════════════
#  শিডিউল ট্যাব ফাংশন
# ════════════════════════════════════════════════

def get_next_buses_table():
    """আজকের পরবর্তী বাসগুলো টেবিল ফরম্যাটে দেয়।"""
    time_info = get_current_time_info()
    bus_data  = load_bus_data()
    next_buses = find_next_buses(bus_data, time_info["total_mins"], time_info["day_bn"], limit=10)

    if not next_buses:
        return (
            f"### আজকের ({time_info['day_bn']}) বাকি কোনো বাস নেই\n"
            f"সময়: {time_info['time_str']}"
        )

    rows = []
    rows.append(f"### 🚌 আজ ({time_info['day_bn']}) পরের বাসগুলো — এখন: {time_info['time_str']}\n")
    rows.append("| # | রুট | ছাড়বে | পৌঁছাবে | কতক্ষণ পরে | ভাড়া |")
    rows.append("|---|-----|--------|---------|------------|------|")
    for i, b in enumerate(next_buses, 1):
        left_str = (
            f"{b['hours_left']}ঘ {b['mins_rem']}মি"
            if b['hours_left']
            else f"{b['mins_rem']}মিনিট"
        )
        rows.append(
            f"| {i} | {b['route_name']} | **{b['departure']}** | {b['arrival']} | {left_str} | {b['fare_bdt']}৳ |"
        )
    return "\n".join(rows)


def get_full_schedule(selected_route: str):
    """নির্বাচিত রুটের সম্পূর্ণ সময়সূচি দেখায়।"""
    bus_data = load_bus_data()
    time_info = get_current_time_info()

    if selected_route == "সব রুট":
        routes = bus_data.get("routes", [])
    else:
        route_id = selected_route.split("|")[0].strip()
        routes = [r for r in bus_data.get("routes", []) if r["route_id"] == route_id]

    if not routes:
        return "কোনো রুট পাওয়া যায়নি।"

    output = []
    for route in routes:
        output.append(f"## {route['route_id']} | {route['route_name']}")
        output.append(f"**{route['from']}** → **{route['to']}**")
        output.append(f"📍 মাধ্যমে: {', '.join(route.get('via', []))}")
        output.append(f"📏 দূরত্ব: {route.get('distance_km', '?')} কিমি | 💰 ভাড়া: {route.get('fare_bdt', '?')} টাকা\n")
        output.append("| ট্রিপ | ছাড়ে | পৌঁছায় | দিনসমূহ |")
        output.append("|------|------|---------|---------|")
        for s in route.get("schedules", []):
            days_str = ", ".join(s.get("days", []))
            output.append(f"| {s['trip_no']} | {s['departure']} | {s['arrival']} | {days_str} |")
        output.append("")
    return "\n".join(output)


def get_route_choices():
    """রুট ড্রপডাউনের জন্য choices তৈরি করে।"""
    bus_data = load_bus_data()
    choices = ["সব রুট"] + [
        f"{r['route_id']} | {r['route_name']}"
        for r in bus_data.get("routes", [])
    ]
    return choices


# ════════════════════════════════════════════════
#  সাইডবার স্ট্যাটাস
# ════════════════════════════════════════════════

def get_status_text() -> str:
    """সাইডবারে মডেল স্ট্যাটাস দেখায়।"""
    m = get_model_info()
    w = get_whisper_info()
    t = get_current_time_info()
    bus_data = load_bus_data()
    route_count = len(bus_data.get("routes", []))

    api_icon = "✅" if m["api_key_set"] else "❌"
    return (
        f"**🤖 LLM:** {m['model_id']}\n\n"
        f"**🔑 API:** {api_icon} {'সেট' if m['api_key_set'] else 'KEY নেই!'}\n\n"
        f"**🎙️ Whisper:** {w['model_size']} ({w['language']})\n\n"
        f"**🕐 সময়:** {t['time_str']} ({t['day_bn']})\n\n"
        f"**📅 তারিখ:** {t['date_str']}\n\n"
        f"**🗺️ রুট:** {route_count}টি রুট লোড\n\n"
        f"**📦 ডেটা:** IIUC বাস সময়সূচি (sample)"
    )


# ════════════════════════════════════════════════
#  কাস্টম CSS
# ════════════════════════════════════════════════

custom_css = """
@import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@300;400;500;600;700&display=swap');

/* ——— বেস স্টাইল ——— */
body, .gradio-container {
    font-family: 'Hind Siliguri', sans-serif !important;
    background: linear-gradient(135deg, #0a1628 0%, #0f2a3f 40%, #1a3a4a 100%) !important;
    min-height: 100vh;
}

/* ——— হেডার ——— */
.app-header {
    text-align: center;
    padding: 1.8rem 2rem;
    background: linear-gradient(135deg, rgba(67,233,123,0.08), rgba(56,249,215,0.05));
    border-radius: 20px;
    backdrop-filter: blur(12px);
    border: 1px solid rgba(67,233,123,0.2);
    margin-bottom: 1.2rem;
    position: relative;
    overflow: hidden;
}
.app-header::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(67,233,123,0.03) 0%, transparent 70%);
    animation: pulse-bg 4s ease-in-out infinite;
}
@keyframes pulse-bg {
    0%, 100% { opacity: 0.5; transform: scale(1); }
    50%       { opacity: 1;   transform: scale(1.05); }
}
.app-header h1 {
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(90deg, #43e97b, #38f9d7, #43e97b);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 3s linear infinite;
    margin: 0;
    position: relative;
}
@keyframes shimmer {
    0%   { background-position: 0% center; }
    100% { background-position: 200% center; }
}
.app-header .subtitle {
    color: #8db4c8;
    margin: 0.5rem 0 0;
    font-size: 1rem;
    position: relative;
}
.app-header .powered-by {
    font-size: 0.78rem;
    color: #4a7a8a;
    margin-top: 0.3rem;
    position: relative;
}

/* ——— চ্যাটবট ——— */
.chatbot {
    border-radius: 16px !important;
    background: rgba(15, 30, 50, 0.6) !important;
    border: 1px solid rgba(67,233,123,0.15) !important;
    backdrop-filter: blur(8px) !important;
}

/* ——— বাটন ——— */
.btn-primary {
    background: linear-gradient(135deg, #43e97b, #38f9d7) !important;
    color: #0a1628 !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    border: none !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease !important;
    font-family: 'Hind Siliguri', sans-serif !important;
}
.btn-primary:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 24px rgba(67,233,123,0.4) !important;
}
.btn-primary:active {
    transform: translateY(0) !important;
}
.btn-next-bus {
    background: linear-gradient(135deg, #f7971e, #ffd200) !important;
    color: #0a1628 !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    border: none !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease !important;
}
.btn-next-bus:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 24px rgba(247,151,30,0.4) !important;
}
.btn-clear {
    background: rgba(255,255,255,0.06) !important;
    color: #8db4c8 !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    transition: background 0.15s !important;
}
.btn-clear:hover {
    background: rgba(255,255,255,0.12) !important;
}
.btn-refresh {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    color: white !important;
    font-weight: 700 !important;
    border-radius: 12px !important;
    border: none !important;
    transition: transform 0.18s ease !important;
}
.btn-refresh:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(102,126,234,0.4) !important;
}

/* ——— স্ট্যাটাস কার্ড ——— */
.status-card {
    background: rgba(15, 30, 50, 0.7) !important;
    border-radius: 14px !important;
    border: 1px solid rgba(67,233,123,0.12) !important;
    padding: 1.2rem !important;
    color: #8db4c8 !important;
    backdrop-filter: blur(8px) !important;
}

/* ——— ইনপুট ফিল্ড ——— */
.gr-textbox textarea, textarea {
    background: rgba(15, 30, 50, 0.7) !important;
    color: #e2f0f7 !important;
    border-color: rgba(67,233,123,0.25) !important;
    border-radius: 12px !important;
    font-family: 'Hind Siliguri', sans-serif !important;
    font-size: 1rem !important;
}
.gr-textbox textarea:focus, textarea:focus {
    border-color: rgba(67,233,123,0.6) !important;
    box-shadow: 0 0 0 3px rgba(67,233,123,0.1) !important;
}

/* ——— অডিও ——— */
.gr-audio {
    border-radius: 14px !important;
    background: rgba(15,30,50,0.6) !important;
    border: 1px solid rgba(67,233,123,0.15) !important;
}

/* ——— ট্যাব ——— */
.tab-nav {
    background: rgba(15,30,50,0.8) !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 4px !important;
}
.tab-nav button {
    border-radius: 10px !important;
    font-family: 'Hind Siliguri', sans-serif !important;
    font-weight: 600 !important;
    transition: all 0.2s !important;
}
.tab-nav button.selected {
    background: linear-gradient(135deg, #43e97b, #38f9d7) !important;
    color: #0a1628 !important;
}

/* ——— ড্রপডাউন ——— */
select, .gr-dropdown select {
    background: rgba(15,30,50,0.8) !important;
    color: #e2f0f7 !important;
    border-color: rgba(67,233,123,0.25) !important;
    border-radius: 12px !important;
    font-family: 'Hind Siliguri', sans-serif !important;
}

/* ——— মার্কডাউন আউটপুট ——— */
.schedule-output {
    background: rgba(15,30,50,0.5) !important;
    border-radius: 14px !important;
    border: 1px solid rgba(67,233,123,0.12) !important;
    padding: 1rem !important;
    color: #c8dde8 !important;
}

/* ——— মাইক্রো অ্যানিমেশন ——— */
.gr-group {
    transition: box-shadow 0.2s ease !important;
}
.gr-group:hover {
    box-shadow: 0 4px 16px rgba(67,233,123,0.08) !important;
}

/* ——— স্ক্রলবার ——— */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: rgba(255,255,255,0.03); }
::-webkit-scrollbar-thumb { background: rgba(67,233,123,0.3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(67,233,123,0.5); }

/* ——— টেবিল স্টাইল ——— */
table { width: 100% !important; border-collapse: collapse !important; }
th {
    background: rgba(67,233,123,0.12) !important;
    color: #43e97b !important;
    padding: 8px 12px !important;
    text-align: left !important;
}
td { padding: 7px 12px !important; border-bottom: 1px solid rgba(255,255,255,0.05) !important; }
tr:hover td { background: rgba(67,233,123,0.04) !important; }

/* ——— ফুটার ——— */
.footer-bar {
    text-align: center;
    padding: 0.8rem;
    margin-top: 0.5rem;
    color: #3d6070;
    font-size: 0.82rem;
    border-top: 1px solid rgba(255,255,255,0.05);
}
"""


# ════════════════════════════════════════════════
#  Gradio UI
# ════════════════════════════════════════════════

with gr.Blocks(
    theme=custom_theme,
    css=custom_css,
    title="কুমিরা বাস বন্ধু — IIUC Bus Assistant",
) as demo:

    # ——— হেডার ———
    gr.HTML("""
    <div class="app-header">
        <h1>🚌 কুমিরা বাস বন্ধু</h1>
        <p class="subtitle">IIUC বাসের সময়সূচি জানতে মাইক্রোফোনে বলুন বা নিচে প্রশ্ন লিখুন</p>
        <p class="powered-by">Powered by Gemma via Gemini API &nbsp;•&nbsp; Whisper STT &nbsp;•&nbsp; Hacktoberfest 2025</p>
    </div>
    """)

    # ——— মেইন ট্যাব ———
    with gr.Tabs(elem_id="main_tabs"):

        # ════ ট্যাব ১: চ্যাট ════
        with gr.Tab("💬 বাস চ্যাটবট", elem_id="tab_chat"):
            with gr.Row():

                # বাম কলাম: চ্যাট
                with gr.Column(scale=3):
                    chatbot = gr.Chatbot(
                        label="💬 কথোপকথন",
                        elem_classes=["chatbot"],
                        height=420,
                        type="messages",
                        avatar_images=(None, "🚌"),
                        show_label=True,
                        elem_id="chatbot_main",
                    )

                    # ভয়েস ইনপুট
                    with gr.Group():
                        gr.Markdown("### 🎙️ মাইক্রোফোনে বলুন")
                        audio_input = gr.Audio(
                            sources=["microphone"],
                            type="numpy",
                            label="রেকর্ড করুন (বাংলায় বলুন)",
                            elem_id="mic_input",
                        )
                        transcribe_btn = gr.Button(
                            "🔊 কথাকে টেক্সটে রূপান্তর করুন",
                            elem_classes=["btn-primary"],
                            elem_id="transcribe_btn",
                        )

                    # টেক্সট ইনপুট
                    with gr.Group():
                        gr.Markdown("### ✍️ অথবা টাইপ করুন")
                        text_input = gr.Textbox(
                            label="আপনার প্রশ্ন",
                            placeholder="যেমন: অক্সিজেন থেকে ভার্সিটির বাস কখন? / নিউমার্কেটের বাস কটায়?",
                            lines=2,
                            elem_id="text_input",
                        )

                    # অ্যাকশন বাটন
                    with gr.Row():
                        send_btn = gr.Button(
                            "📩 জিজ্ঞেস করুন",
                            variant="primary",
                            elem_classes=["btn-primary"],
                            elem_id="send_btn",
                            scale=2,
                        )
                        next_bus_btn = gr.Button(
                            "⏰ পরের বাস",
                            elem_classes=["btn-next-bus"],
                            elem_id="next_bus_btn",
                            scale=1,
                        )
                        clear_btn = gr.Button(
                            "🗑️ মুছুন",
                            elem_classes=["btn-clear"],
                            elem_id="clear_btn",
                            scale=1,
                        )

                # ডান কলাম: স্ট্যাটাস + উদাহরণ
                with gr.Column(scale=1):
                    gr.Markdown("### ℹ️ সিস্টেম তথ্য")
                    status_md = gr.Markdown(
                        value=get_status_text(),
                        elem_classes=["status-card"],
                        elem_id="status_card",
                    )

                    gr.Markdown("### 💡 উদাহরণ প্রশ্ন")
                    gr.Examples(
                        examples=[
                            ["নিউমার্কেটের বাস কখন ছাড়ে?"],
                            ["আজকে পরের বাস কখন?"],
                            ["আগ্রাবাদ রুটের সময়সূচি দাও"],
                            ["ফেনীর বাস আছে কি?"],
                            ["শুক্রবার কি বাস চলে?"],
                            ["হাটহাজারীর বাস কটায়?"],
                            ["নোয়াখালীর বাস কখন?"],
                            ["বাস ভাড়া কত?"],
                            ["অক্সিজেন থেকে কোন বাস ধরব?"],
                        ],
                        inputs=text_input,
                        label="ক্লিক করে প্রশ্ন করুন",
                        elem_id="examples_section",
                    )

                    gr.Markdown(
                        "> ⚠️ **নোট:** ডেটা sample/made-up। "
                        "প্রকৃত সময়সূচি `data/buses.json` এ আপডেট করুন।",
                        elem_id="data_note",
                    )

        # ════ ট্যাব ২: শিডিউল বোর্ড ════
        with gr.Tab("📋 আজকের শিডিউল", elem_id="tab_schedule"):
            gr.Markdown("## 🚌 আজকের পরবর্তী বাসগুলো")
            gr.Markdown("রিয়েল-টাইম বাংলাদেশ সময় অনুযায়ী আপডেট হয়।")

            with gr.Row():
                refresh_btn = gr.Button(
                    "🔄 রিফ্রেশ করুন",
                    elem_classes=["btn-refresh"],
                    elem_id="refresh_schedule_btn",
                    scale=1,
                )

            next_bus_output = gr.Markdown(
                value=get_next_buses_table(),
                elem_classes=["schedule-output"],
                elem_id="next_bus_table",
            )

            gr.Markdown("---")
            gr.Markdown("## 📑 রুট অনুযায়ী সম্পূর্ণ শিডিউল")

            route_choices = get_route_choices()
            route_dropdown = gr.Dropdown(
                choices=route_choices,
                value="সব রুট",
                label="রুট নির্বাচন করুন",
                elem_id="route_dropdown",
            )

            full_schedule_output = gr.Markdown(
                value=get_full_schedule("সব রুট"),
                elem_classes=["schedule-output"],
                elem_id="full_schedule_output",
            )

        # ════ ট্যাব ৩: রুট এক্সপ্লোরার ════
        with gr.Tab("🗺️ রুট তথ্য", elem_id="tab_routes"):
            gr.Markdown("## 🗺️ সমস্ত রুটের তথ্য")

            # রুট কার্ড
            bus_data_preview = load_bus_data()
            route_cards_html = """<div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:1rem; padding:0.5rem;">"""

            colors = [
                ("#43e97b", "#38f9d7"),
                ("#f7971e", "#ffd200"),
                ("#667eea", "#764ba2"),
                ("#11998e", "#38ef7d"),
                ("#ee0979", "#ff6a00"),
                ("#4776e6", "#8e54e9"),
            ]

            for i, route in enumerate(bus_data_preview.get("routes", [])):
                c1, c2 = colors[i % len(colors)]
                trip_count = len(route.get("schedules", []))
                via_text = " → ".join(route.get("via", [])[:3])
                if len(route.get("via", [])) > 3:
                    via_text += " → ..."

                route_cards_html += f"""
                <div style="
                    background: linear-gradient(135deg, rgba(15,30,50,0.8), rgba(20,40,65,0.8));
                    border: 1px solid {c1}33;
                    border-radius: 16px;
                    padding: 1.2rem;
                    backdrop-filter: blur(8px);
                    transition: transform 0.2s, box-shadow 0.2s;
                    cursor: default;
                " onmouseover="this.style.transform='translateY(-4px)';this.style.boxShadow='0 8px 24px {c1}22'"
                   onmouseout="this.style.transform='translateY(0)';this.style.boxShadow='none'">
                    <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.8rem;">
                        <span style="
                            background: linear-gradient(135deg, {c1}, {c2});
                            color: #0a1628;
                            font-weight: 700;
                            font-size: 0.8rem;
                            padding: 3px 10px;
                            border-radius: 20px;
                        ">{route['route_id']}</span>
                        <span style="color:{c1}; font-size:1.1rem;">🚌</span>
                    </div>
                    <h3 style="color:#e2f0f7; font-size:0.95rem; margin:0 0 0.5rem; font-family:'Hind Siliguri',sans-serif;">{route['route_name']}</h3>
                    <p style="color:#6b9aab; font-size:0.82rem; margin:0.3rem 0;">📍 {via_text}</p>
                    <div style="display:flex; gap:1rem; margin-top:0.8rem; font-size:0.85rem;">
                        <span style="color:{c1};">🕐 {trip_count} ট্রিপ</span>
                        <span style="color:#8db4c8;">📏 {route.get('distance_km','?')} কিমি</span>
                        <span style="color:#f7971e;">💰 {route.get('fare_bdt','?')}৳</span>
                    </div>
                </div>
                """

            route_cards_html += "</div>"

            gr.HTML(route_cards_html)

            gr.Markdown("---")
            gr.Markdown("## 📌 বিশেষ নোট")

            notes_md = "\n".join(
                f"- {note}"
                for note in bus_data_preview.get("special_notes", [])
            )
            gr.Markdown(notes_md)

            gr.Markdown("---")
            gr.Markdown("## 📞 যোগাযোগ")
            contact = bus_data_preview.get("contact", {})
            gr.Markdown(
                f"**অফিস:** {contact.get('transport_office', '')}  \n"
                f"**ফোন:** {contact.get('phone', '')}  \n"
                f"**অবস্থান:** {contact.get('location', '')}  \n"
                f"**সময়:** {contact.get('office_hours', '')}"
            )

    # ——— ফুটার ———
    gr.HTML("""
    <div class="footer-bar">
        🏆 Hacktoberfest Hack Day Chittagong × IEEE CS IIUC SBC &nbsp;|&nbsp;
        Made with ❤️ for IIUC students &nbsp;|&nbsp;
        Powered by <strong>Gemma</strong> (Gemini API) + <strong>Whisper</strong> STT
    </div>
    """)


    # ════════════════════════════════════════════════
    #  ইভেন্ট হ্যান্ডলার
    # ════════════════════════════════════════════════

    # ভয়েস → টেক্সট
    transcribe_btn.click(
        fn=process_voice,
        inputs=[audio_input],
        outputs=[text_input, chatbot],
    )

    # টেক্সট সাবমিট (বাটন)
    send_btn.click(
        fn=ask_question,
        inputs=[text_input, chatbot],
        outputs=[chatbot, text_input],
    )

    # Enter চাপলেও সাবমিট
    text_input.submit(
        fn=ask_question,
        inputs=[text_input, chatbot],
        outputs=[chatbot, text_input],
    )

    # পরের বাস বাটন
    next_bus_btn.click(
        fn=ask_next_bus,
        inputs=[chatbot],
        outputs=[chatbot, text_input],
    )

    # মুছুন
    clear_btn.click(
        fn=clear_chat,
        outputs=[chatbot, text_input],
    )

    # শিডিউল রিফ্রেশ
    refresh_btn.click(
        fn=get_next_buses_table,
        outputs=[next_bus_output],
    )

    # রুট ড্রপডাউন পরিবর্তন
    route_dropdown.change(
        fn=get_full_schedule,
        inputs=[route_dropdown],
        outputs=[full_schedule_output],
    )


# ════════════════════════════════════════════════
#  এন্ট্রিপয়েন্ট
# ════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 55)
    print(f"  {APP_TITLE}  v{APP_VERSION}")
    print("=" * 55)
    info  = get_model_info()
    winfo = get_whisper_info()
    bus   = load_bus_data()
    print(f"  LLM    : {info['model_id']} ({info['provider']})")
    print(f"  STT    : Whisper {winfo['model_size']} | ভাষা: {winfo['language']}")
    print(f"  API    : {'✅ সেট' if info['api_key_set'] else '❌ GEMINI_API_KEY সেট নেই!'}")
    print(f"  Routes : {len(bus.get('routes', []))} টি রুট লোড হয়েছে")
    print("=" * 55)
    print("  ব্রাউজার: http://localhost:7860")
    print("=" * 55)

    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", 7860)),
        share=False,
        show_error=True,
        inbrowser=True,
    )
