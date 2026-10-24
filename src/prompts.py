"""
prompts.py — নিয়মকানুন + বর্তমান সময় + বাস ডেটা মিলিয়ে প্রম্পট তৈরি করে।
স্মার্ট next-bus detection ও pickup-point awareness সহ।
"""

import json
from datetime import datetime
from pathlib import Path

import pytz

# বাংলাদেশ টাইমজোন
BD_TZ = pytz.timezone("Asia/Dhaka")

# বার বাংলায়
BANGLA_DAYS = {
    "Monday":    "সোমবার",
    "Tuesday":   "মঙ্গলবার",
    "Wednesday": "বুধবার",
    "Thursday":  "বৃহস্পতিবার",
    "Friday":    "শুক্রবার",
    "Saturday":  "শনিবার",
    "Sunday":    "রবিবার",
}

# buses.json এর পাথ
_DATA_PATH = Path(__file__).parent.parent / "data" / "buses.json"


def load_bus_data() -> dict:
    """buses.json লোড করে dict হিসেবে ফেরত দেয়।"""
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_current_time_info() -> dict:
    """বর্তমান বাংলাদেশ সময় ও বার রিটার্ন করে।"""
    now = datetime.now(BD_TZ)
    day_en = now.strftime("%A")
    return {
        "time_str":   now.strftime("%H:%M"),
        "date_str":   now.strftime("%d %B %Y"),
        "day_en":     day_en,
        "day_bn":     BANGLA_DAYS.get(day_en, day_en),
        "hour":       now.hour,
        "minute":     now.minute,
        "total_mins": now.hour * 60 + now.minute,
        "is_friday":  day_en == "Friday",
        "is_weekend":  day_en in ("Friday", "Saturday"),
    }


def _parse_time_to_mins(t: str) -> int:
    """'HH:MM' → মিনিটে রূপান্তর।"""
    h, m = map(int, t.split(":"))
    return h * 60 + m


def find_next_buses(bus_data: dict, current_mins: int, current_day_bn: str, limit: int = 5) -> list[dict]:
    """
    আজকের বাকি ট্রিপগুলো খুঁজে বের করে (সবচেয়ে কাছেরগুলো আগে)।
    """
    upcoming = []
    for route in bus_data.get("routes", []):
        for sched in route.get("schedules", []):
            if current_day_bn not in sched.get("days", []):
                continue
            dep_total = _parse_time_to_mins(sched["departure"])
            if dep_total > current_mins:
                mins_left = dep_total - current_mins
                upcoming.append({
                    "route_id":     route["route_id"],
                    "route_name":   route["route_name"],
                    "from":         route["from"],
                    "to":           route["to"],
                    "via":          ", ".join(route.get("via", [])),
                    "departure":    sched["departure"],
                    "arrival":      sched["arrival"],
                    "fare_bdt":     route.get("fare_bdt", "?"),
                    "minutes_left": mins_left,
                    "hours_left":   mins_left // 60,
                    "mins_rem":     mins_left % 60,
                })
    upcoming.sort(key=lambda x: x["minutes_left"])
    return upcoming[:limit]


def find_buses_by_destination(bus_data: dict, destination_keyword: str, day_bn: str) -> list[dict]:
    """
    গন্তব্য কীওয়ার্ড দিয়ে রুট খোঁজে (case-insensitive)।
    """
    matches = []
    kw = destination_keyword.lower()
    for route in bus_data.get("routes", []):
        # রুট নাম, from, to বা via তে কীওয়ার্ড আছে কিনা চেক করে
        searchable = " ".join([
            route.get("route_name", ""),
            route.get("from", ""),
            route.get("to", ""),
            " ".join(route.get("via", [])),
        ]).lower()

        if kw in searchable:
            route_info = {**route}
            # শুধু আজকের schedules রাখো
            route_info["todays_schedules"] = [
                s for s in route.get("schedules", [])
                if day_bn in s.get("days", [])
            ]
            if route_info["todays_schedules"]:
                matches.append(route_info)
    return matches


def format_bus_data_for_prompt(bus_data: dict, time_info: dict) -> str:
    """
    বাস ডেটাকে LLM-বান্ধব টেক্সটে রূপান্তর করে।
    সম্পূর্ণ রুট তালিকা + আজকের পরবর্তী বাসগুলো।
    """
    lines = []

    # ===== সমস্ত রুট =====
    lines.append("## সমস্ত বাস রুট ও সময়সূচি\n")
    for route in bus_data.get("routes", []):
        fare = route.get("fare_bdt", "?")
        dist = route.get("distance_km", "?")
        lines.append(f"### {route['route_id']} | {route['route_name']}")
        lines.append(f"- **রুট:** {route['from']} → {route['to']}")
        lines.append(f"- **মাধ্যমে:** {', '.join(route.get('via', []))}")
        lines.append(f"- **দূরত্ব:** {dist} কিমি | **ভাড়া:** {fare} টাকা")
        lines.append("- **ট্রিপ:**")
        for s in route.get("schedules", []):
            days_str = ", ".join(s.get("days", []))
            lines.append(
                f"  - ট্রিপ {s['trip_no']}: ছাড়ে **{s['departure']}**, পৌঁছায় {s['arrival']}  |  দিন: {days_str}"
            )
        lines.append("")

    # ===== পিকআপ পয়েন্ট =====
    pickup = bus_data.get("pickup_points", {})
    if pickup:
        lines.append("## পিকআপ পয়েন্ট (গুরুত্বপূর্ণ স্টপেজ)")
        for area, points in pickup.items():
            lines.append(f"- **{area}:** {', '.join(points)}")
        lines.append("")

    # ===== বিশেষ নোট =====
    notes = bus_data.get("special_notes", [])
    if notes:
        lines.append("## বিশেষ নোট ও নিয়মকানুন")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    # ===== পরবর্তী বাস (আজ) =====
    next_buses = find_next_buses(
        bus_data,
        time_info["total_mins"],
        time_info["day_bn"],
        limit=5,
    )
    if next_buses:
        lines.append(
            f"## 🚌 আজ ({time_info['day_bn']}) পরবর্তী বাসগুলো "
            f"(বর্তমান সময়: {time_info['time_str']})"
        )
        for b in next_buses:
            left_str = f"{b['hours_left']}ঘন্টা {b['mins_rem']}মিনিট" if b['hours_left'] else f"{b['mins_rem']}মিনিট"
            lines.append(
                f"- [{b['route_id']}] {b['route_name']}  →  ছাড়বে **{b['departure']}** ({left_str} পরে) | ভাড়া: {b['fare_bdt']}টাকা"
            )
    else:
        lines.append(
            f"## আজকের ({time_info['day_bn']}) বাকি বাস নেই "
            f"(বর্তমান সময়: {time_info['time_str']})"
        )

    # ===== যোগাযোগ =====
    contact = bus_data.get("contact", {})
    if contact:
        lines.append("\n## যোগাযোগ")
        lines.append(f"- **অফিস:** {contact.get('transport_office', '')}")
        lines.append(f"- **ফোন:** {contact.get('phone', '')}")
        lines.append(f"- **অবস্থান:** {contact.get('location', '')}")
        lines.append(f"- **সময়:** {contact.get('office_hours', '')}")

    return "\n".join(lines)


def build_system_prompt() -> str:
    """
    সম্পূর্ণ system prompt তৈরি করে।
    নিয়মকানুন + বর্তমান সময় + বাস ডেটা একসাথে।
    """
    time_info = get_current_time_info()
    bus_data  = load_bus_data()
    bus_text  = format_bus_data_for_prompt(bus_data, time_info)

    friday_note = ""
    if time_info["is_friday"]:
        friday_note = "\n⚠️ আজ শুক্রবার — সীমিত সার্ভিস। জুম্মার নামাজের সময় (১২:০০-১৩:৩০) বাস নেই।"

    system_prompt = f"""তুমি **কুমিরা বাস বন্ধু** — IIUC (International Islamic University Chittagong) এর ছাত্রছাত্রীদের বাস সহকারী।{friday_note}

## তোমার পরিচয়
- নাম: কুমিরা বাস বন্ধু 🚌
- কাজ: IIUC বাস সময়সূচি ও রুট সম্পর্কে সঠিক, সহায়ক উত্তর দেওয়া।
- ভাষা: বাংলায় কথা বলো। ইংরেজি প্রশ্নেও বাংলায় উত্তর দাও।
- টোন: বন্ধুসুলভ, সংক্ষিপ্ত ও সহায়ক।

## বর্তমান তথ্য
- তারিখ: {time_info['date_str']}
- সময়: {time_info['time_str']} (বাংলাদেশ সময়, GMT+6)
- আজকের বার: {time_info['day_bn']}

## নিয়মকানুন (অবশ্যই মেনে চলবে)
1. **শুধুমাত্র** নিচের বাস ডেটার উপর ভিত্তি করে উত্তর দাও। অনুমান করো না।
2. ডেটায় না থাকলে সরাসরি বলো: "এই তথ্য আমার কাছে নেই, Transport Office-এ যোগাযোগ করুন।"
3. "পরের বাস" বা সময় জিজ্ঞেস করলে বর্তমান সময় ({time_info['time_str']}) থেকে হিসাব করে উত্তর দাও।
4. বাস তথ্য সবসময় **বুলেট বা টেবিল** ফরম্যাটে দাও — পড়তে সহজ হবে।
5. ভাড়া ও দূরত্বের তথ্য দিতে ভুলো না।
6. একাধিক রুট থাকলে সবগুলো দেখাও।
7. ডেটা sample/made-up — ব্যবহারকারী জিজ্ঞেস করলে সততার সাথে বলো।
8. জরুরি তথ্যের জন্য Transport Office-এর কথা উল্লেখ করো।

## বাস ডেটা (সম্পূর্ণ তথ্য)
{bus_text}
"""
    return system_prompt


def build_user_message(user_input: str) -> str:
    """ব্যবহারকারীর প্রশ্ন হুবহু ফেরত দেয় (ভবিষ্যতে preprocessing যোগ করা যাবে)।"""
    return user_input.strip()
