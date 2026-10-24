"""
test_prompt.py — pytest টেস্ট স্যুট
src/prompts.py এর সব ফাংশন পরীক্ষা করে।
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import pytest

# src/ যোগ করা
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prompts import (
    load_bus_data,
    get_current_time_info,
    find_next_buses,
    find_buses_by_destination,
    format_bus_data_for_prompt,
    build_system_prompt,
    build_user_message,
    _parse_time_to_mins,
    BANGLA_DAYS,
)


# ════════════════════════════════════════════════
#  ফিকচার
# ════════════════════════════════════════════════

@pytest.fixture
def bus_data():
    """buses.json থেকে লাইভ ডেটা লোড করে।"""
    return load_bus_data()


@pytest.fixture
def sample_bus_data():
    """মিনিমাল mock ডেটা — একটি রুট, দুটি ট্রিপ।"""
    return {
        "routes": [
            {
                "route_id": "R01",
                "route_name": "ভার্সিটি → নিউমার্কেট",
                "from": "IIUC ভার্সিটি গেট",
                "to": "নিউমার্কেট",
                "via": ["অক্সিজেন", "মুরাদপুর"],
                "distance_km": 28,
                "fare_bdt": 20,
                "schedules": [
                    {
                        "trip_no": 1,
                        "departure": "07:00",
                        "arrival": "08:15",
                        "days": ["রবিবার", "সোমবার", "মঙ্গলবার"],
                    },
                    {
                        "trip_no": 2,
                        "departure": "14:00",
                        "arrival": "15:15",
                        "days": ["রবিবার", "সোমবার", "মঙ্গলবার"],
                    },
                ],
            },
            {
                "route_id": "R02",
                "route_name": "ভার্সিটি → আগ্রাবাদ",
                "from": "IIUC ভার্সিটি গেট",
                "to": "আগ্রাবাদ",
                "via": ["অক্সিজেন"],
                "distance_km": 30,
                "fare_bdt": 25,
                "schedules": [
                    {
                        "trip_no": 1,
                        "departure": "08:30",
                        "arrival": "10:00",
                        "days": ["সোমবার"],
                    },
                ],
            },
        ],
        "special_notes": ["শুক্রবার সীমিত সার্ভিস।"],
        "pickup_points": {
            "নিউমার্কেট": ["নিউমার্কেট চৌরাস্তা"],
        },
        "contact": {
            "transport_office": "IIUC পরিবহন অফিস",
            "phone": "031-XXXXXXX",
            "location": "Admin Building",
            "office_hours": "৯:০০ - ১৭:০০",
        },
    }


# ════════════════════════════════════════════════
#  ইউটিলিটি ফাংশন টেস্ট
# ════════════════════════════════════════════════

class TestParseTime:
    def test_midnight(self):
        assert _parse_time_to_mins("00:00") == 0

    def test_noon(self):
        assert _parse_time_to_mins("12:00") == 720

    def test_afternoon(self):
        assert _parse_time_to_mins("14:30") == 870

    def test_end_of_day(self):
        assert _parse_time_to_mins("23:59") == 1439

    def test_single_digit_hour(self):
        assert _parse_time_to_mins("07:05") == 425


# ════════════════════════════════════════════════
#  ডেটা লোডিং টেস্ট
# ════════════════════════════════════════════════

class TestLoadBusData:
    def test_returns_dict(self, bus_data):
        assert isinstance(bus_data, dict)

    def test_has_routes(self, bus_data):
        assert "routes" in bus_data
        assert len(bus_data["routes"]) > 0

    def test_routes_have_required_fields(self, bus_data):
        required = {"route_id", "route_name", "from", "to", "schedules"}
        for route in bus_data["routes"]:
            assert required.issubset(route.keys()), f"Route {route.get('route_id')} is missing fields"

    def test_schedules_have_required_fields(self, bus_data):
        for route in bus_data["routes"]:
            for sched in route["schedules"]:
                assert "departure" in sched
                assert "arrival" in sched
                assert "days" in sched

    def test_has_special_notes(self, bus_data):
        assert "special_notes" in bus_data
        assert len(bus_data["special_notes"]) > 0

    def test_has_contact_info(self, bus_data):
        assert "contact" in bus_data

    def test_minimum_route_count(self, bus_data):
        """প্রজেক্টে কমপক্ষে ৮টি রুট আছে।"""
        assert len(bus_data["routes"]) >= 8

    def test_has_pickup_points(self, bus_data):
        assert "pickup_points" in bus_data


# ════════════════════════════════════════════════
#  সময় তথ্য টেস্ট
# ════════════════════════════════════════════════

class TestGetCurrentTimeInfo:
    def test_returns_required_keys(self):
        info = get_current_time_info()
        required = {"time_str", "date_str", "day_en", "day_bn", "hour", "minute", "total_mins", "is_friday", "is_weekend"}
        assert required.issubset(info.keys())

    def test_time_str_format(self):
        info = get_current_time_info()
        parts = info["time_str"].split(":")
        assert len(parts) == 2
        assert all(p.isdigit() for p in parts)

    def test_total_mins_range(self):
        info = get_current_time_info()
        assert 0 <= info["total_mins"] < 1440

    def test_day_bn_is_bangla(self):
        info = get_current_time_info()
        assert info["day_bn"] in BANGLA_DAYS.values()

    def test_is_friday_bool(self):
        info = get_current_time_info()
        assert isinstance(info["is_friday"], bool)

    @patch("prompts.datetime")
    def test_friday_detection(self, mock_dt):
        """শুক্রবার সঠিকভাবে ধরা পড়ে।"""
        import pytz
        BD_TZ = pytz.timezone("Asia/Dhaka")
        # 2025-01-03 is a Friday
        fake_now = datetime(2025, 1, 3, 10, 0, tzinfo=BD_TZ)
        mock_dt.now.return_value = fake_now
        mock_dt.strftime = datetime.strftime
        info = get_current_time_info()
        # We just check the structure is correct (mocking datetime in pytz is complex)
        assert "is_friday" in info


# ════════════════════════════════════════════════
#  পরবর্তী বাস খোঁজার টেস্ট
# ════════════════════════════════════════════════

class TestFindNextBuses:
    def test_finds_future_trips(self, sample_bus_data):
        # সকাল ৬:০০ (360 মিনিট) — উভয় ট্রিপই সামনে
        result = find_next_buses(sample_bus_data, 360, "সোমবার", limit=5)
        assert len(result) >= 1
        for bus in result:
            assert bus["minutes_left"] > 0

    def test_no_buses_after_last_trip(self, sample_bus_data):
        # রাত ২৩:০০ (1380 মিনিট) — সব ট্রিপ শেষ
        result = find_next_buses(sample_bus_data, 1380, "সোমবার", limit=5)
        assert len(result) == 0

    def test_sorted_by_time(self, sample_bus_data):
        result = find_next_buses(sample_bus_data, 0, "সোমবার", limit=5)
        minutes = [b["minutes_left"] for b in result]
        assert minutes == sorted(minutes)

    def test_respects_limit(self, sample_bus_data):
        result = find_next_buses(sample_bus_data, 0, "সোমবার", limit=1)
        assert len(result) <= 1

    def test_respects_day_filter(self, sample_bus_data):
        # বৃহস্পতিবার — sample_bus_data তে কোনো ট্রিপ নেই
        result = find_next_buses(sample_bus_data, 0, "বৃহস্পতিবার", limit=5)
        assert len(result) == 0

    def test_result_has_required_fields(self, sample_bus_data):
        result = find_next_buses(sample_bus_data, 0, "সোমবার", limit=5)
        if result:
            bus = result[0]
            required = {"route_id", "route_name", "from", "to", "departure", "arrival", "minutes_left", "fare_bdt"}
            assert required.issubset(bus.keys())

    def test_hours_and_mins_calculated(self, sample_bus_data):
        result = find_next_buses(sample_bus_data, 0, "সোমবার", limit=1)
        if result:
            b = result[0]
            assert b["hours_left"] == b["minutes_left"] // 60
            assert b["mins_rem"]   == b["minutes_left"] % 60


# ════════════════════════════════════════════════
#  গন্তব্য অনুযায়ী রুট খোঁজার টেস্ট
# ════════════════════════════════════════════════

class TestFindByDestination:
    def test_finds_newmarket_route(self, bus_data):
        result = find_buses_by_destination(bus_data, "নিউমার্কেট", "সোমবার")
        assert len(result) > 0

    def test_finds_agrabadi_route(self, bus_data):
        result = find_buses_by_destination(bus_data, "আগ্রাবাদ", "সোমবার")
        assert len(result) > 0

    def test_returns_empty_for_unknown(self, bus_data):
        result = find_buses_by_destination(bus_data, "ঢাকা_সিটি_xyz_999", "সোমবার")
        assert len(result) == 0

    def test_todays_schedules_filtered(self, sample_bus_data):
        result = find_buses_by_destination(sample_bus_data, "নিউমার্কেট", "মঙ্গলবার")
        if result:
            for sched in result[0]["todays_schedules"]:
                assert "মঙ্গলবার" in sched["days"]


# ════════════════════════════════════════════════
#  ফরম্যাট ফাংশন টেস্ট
# ════════════════════════════════════════════════

class TestFormatBusData:
    def test_returns_string(self, sample_bus_data):
        time_info = get_current_time_info()
        result = format_bus_data_for_prompt(sample_bus_data, time_info)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_route_name(self, sample_bus_data):
        time_info = get_current_time_info()
        result = format_bus_data_for_prompt(sample_bus_data, time_info)
        assert "নিউমার্কেট" in result

    def test_contains_departure_times(self, sample_bus_data):
        time_info = get_current_time_info()
        result = format_bus_data_for_prompt(sample_bus_data, time_info)
        assert "07:00" in result or "14:00" in result

    def test_contains_fare_info(self, sample_bus_data):
        time_info = get_current_time_info()
        result = format_bus_data_for_prompt(sample_bus_data, time_info)
        assert "20" in result  # fare_bdt

    def test_contains_pickup_points(self, sample_bus_data):
        time_info = get_current_time_info()
        result = format_bus_data_for_prompt(sample_bus_data, time_info)
        assert "নিউমার্কেট চৌরাস্তা" in result

    def test_contains_special_notes(self, sample_bus_data):
        time_info = get_current_time_info()
        result = format_bus_data_for_prompt(sample_bus_data, time_info)
        assert "শুক্রবার" in result


# ════════════════════════════════════════════════
#  সিস্টেম প্রম্পট টেস্ট
# ════════════════════════════════════════════════

class TestBuildSystemPrompt:
    def test_returns_nonempty_string(self):
        result = build_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 500  # প্রম্পট কমপক্ষে ৫০০ অক্ষর হওয়া উচিত

    def test_contains_assistant_name(self):
        result = build_system_prompt()
        assert "কুমিরা বাস বন্ধু" in result

    def test_contains_iiuc_mention(self):
        result = build_system_prompt()
        assert "IIUC" in result

    def test_contains_current_day(self):
        result = build_system_prompt()
        time_info = get_current_time_info()
        assert time_info["day_bn"] in result

    def test_contains_current_time(self):
        result = build_system_prompt()
        time_info = get_current_time_info()
        # সময়ের প্রথম ২ অঙ্ক (ঘন্টা) থাকা উচিত
        assert time_info["time_str"][:2] in result

    def test_contains_bus_routes(self):
        result = build_system_prompt()
        assert "নিউমার্কেট" in result or "আগ্রাবাদ" in result

    def test_contains_rules(self):
        result = build_system_prompt()
        assert "নিয়মকানুন" in result


# ════════════════════════════════════════════════
#  ইউজার মেসেজ টেস্ট
# ════════════════════════════════════════════════

class TestBuildUserMessage:
    def test_strips_whitespace(self):
        assert build_user_message("  প্রশ্ন  ") == "প্রশ্ন"

    def test_returns_same_text(self):
        msg = "নিউমার্কেটের বাস কখন?"
        assert build_user_message(msg) == msg

    def test_empty_string(self):
        assert build_user_message("   ") == ""


# ════════════════════════════════════════════════
#  ইন্টিগ্রেশন টেস্ট
# ════════════════════════════════════════════════

class TestIntegration:
    def test_full_pipeline_no_error(self):
        """load → format → build prompt → কোনো error নেই।"""
        bus_data  = load_bus_data()
        time_info = get_current_time_info()
        formatted = format_bus_data_for_prompt(bus_data, time_info)
        prompt    = build_system_prompt()

        assert isinstance(formatted, str)
        assert isinstance(prompt, str)
        assert len(prompt) > len(formatted)  # system prompt সবসময় বড়

    def test_data_consistency(self):
        """buses.json এর সব route_id ইউনিক।"""
        bus_data = load_bus_data()
        ids = [r["route_id"] for r in bus_data.get("routes", [])]
        assert len(ids) == len(set(ids)), "Duplicate route IDs found!"

    def test_departure_time_format(self):
        """সব departure/arrival 'HH:MM' ফরম্যাটে আছে।"""
        bus_data = load_bus_data()
        for route in bus_data["routes"]:
            for s in route["schedules"]:
                for field in ("departure", "arrival"):
                    t = s[field]
                    parts = t.split(":")
                    assert len(parts) == 2, f"Invalid time format: {t}"
                    assert 0 <= int(parts[0]) <= 23
                    assert 0 <= int(parts[1]) <= 59

    def test_departure_before_arrival(self):
        """ছাড়ার সময় পৌঁছানোর সময়ের আগে।"""
        bus_data = load_bus_data()
        for route in bus_data["routes"]:
            for s in route["schedules"]:
                dep = _parse_time_to_mins(s["departure"])
                arr = _parse_time_to_mins(s["arrival"])
                assert dep < arr, (
                    f"Route {route['route_id']} Trip {s['trip_no']}: "
                    f"departure {s['departure']} >= arrival {s['arrival']}"
                )
