import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

st.set_page_config(page_title="PTO Calculator", layout="wide")

FREQUENCY_TO_WEEKS = {
    "week": 1.0,
    "every 2 weeks": 2.0,
    "twice a month": 52.0 / 24.0,
    "month": 52.0 / 12.0,
    "year": 52.0,
}
WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
WORK_SCHEDULE_OPTIONS = [
    "Mon-Fri 8 hours",
    "9/80",
    "Custom",
]
PTO_FORM_FIELDS = {
    "name": "pto_form_name",
    "current_balance": "pto_form_current_balance",
    "balance_unit": "pto_form_balance_unit",
    "accrual_amount": "pto_form_accrual_amount",
    "accrual_unit": "pto_form_accrual_unit",
    "accrual_frequency": "pto_form_accrual_frequency",
    "accrual_cap": "pto_form_accrual_cap",
    "rollover_limit": "pto_form_rollover_limit",
}
TIME_OFF_FORM_FIELDS = {
    "start_date": "time_off_form_start_date",
    "end_date": "time_off_form_end_date",
    "pto_type": "time_off_form_pto_type",
    "reason": "time_off_form_reason",
}


def hours_from_value(amount: float, unit: str, pto_day_hours_value: float) -> float:
    if unit == "hours":
        return float(amount)
    return float(amount) * float(pto_day_hours_value)


def days_from_hours(hours: float, pto_day_hours_value: float) -> float:
    return float(hours) / float(pto_day_hours_value)


def accrual_hours_per_week(amount: float, unit: str, frequency: str, pto_day_hours_value: float) -> float:
    hours = hours_from_value(amount, unit, pto_day_hours_value)
    return hours / FREQUENCY_TO_WEEKS[frequency]


def normalize_optional_limit(value) -> float | None:
    if value in (None, "", "none"):
        return None
    limit = float(value)
    if limit < 0:
        raise ValueError("Cap and rollover limits cannot be negative.")
    return limit


def limit_hours(limit_value: float | None, unit: str, pto_day_hours_value: float) -> float | None:
    if limit_value is None:
        return None
    return hours_from_value(limit_value, unit, pto_day_hours_value)


def normalize_accrual_frequency(frequency: str) -> str:
    return {"bi-weekly": "every 2 weeks"}.get(frequency, frequency)


def monday_of(day_value: date) -> date:
    return day_value - timedelta(days=day_value.weekday())


def date_range(start_value: date, end_value: date):
    cursor = start_value
    while cursor <= end_value:
        yield cursor
        cursor += timedelta(days=1)


def nth_weekday_of_month(year: int, month: int, weekday: int, occurrence: int) -> date:
    first_day = date(year, month, 1)
    offset = (weekday - first_day.weekday()) % 7
    return first_day + timedelta(days=offset + (occurrence - 1) * 7)


def last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    cursor = next_month - timedelta(days=1)
    while cursor.weekday() != weekday:
        cursor -= timedelta(days=1)
    return cursor


def observed_date(day_value: date) -> date:
    if day_value.weekday() == 5:
        return day_value - timedelta(days=1)
    if day_value.weekday() == 6:
        return day_value + timedelta(days=1)
    return day_value


def us_federal_holidays(year: int) -> list[dict]:
    holidays = [
        {"label": "New Year's Day", "date": observed_date(date(year, 1, 1))},
        {"label": "Martin Luther King Jr. Day", "date": nth_weekday_of_month(year, 1, 0, 3)},
        {"label": "Washington's Birthday", "date": nth_weekday_of_month(year, 2, 0, 3)},
        {"label": "Memorial Day", "date": last_weekday_of_month(year, 5, 0)},
        {"label": "Juneteenth", "date": observed_date(date(year, 6, 19))},
        {"label": "Independence Day", "date": observed_date(date(year, 7, 4))},
        {"label": "Labor Day", "date": nth_weekday_of_month(year, 9, 0, 1)},
        {"label": "Columbus Day", "date": nth_weekday_of_month(year, 10, 0, 2)},
        {"label": "Veterans Day", "date": observed_date(date(year, 11, 11))},
        {"label": "Thanksgiving Day", "date": nth_weekday_of_month(year, 11, 3, 4)},
        {"label": "Christmas Day", "date": observed_date(date(year, 12, 25))},
    ]
    holidays.sort(key=lambda item: item["date"])
    return holidays


def holiday_options_for_projection(start_date_value: date, weeks_to_project_value: int = 52) -> list[dict]:
    projection_end = start_date_value + timedelta(weeks=weeks_to_project_value)
    options = []
    seen = set()
    for year in range(start_date_value.year, projection_end.year + 1):
        for holiday in us_federal_holidays(year):
            key = holiday["date"].isoformat()
            if key not in seen and start_date_value <= holiday["date"] <= projection_end:
                seen.add(key)
                options.append(holiday)
    return options


def custom_holiday_options(custom_holidays: list[dict]) -> list[dict]:
    options = []
    for entry in custom_holidays:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label", "")).strip()
        raw_date = entry.get("date")
        if not label or raw_date is None:
            continue
        try:
            holiday_date = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date))
        except ValueError:
            continue
        options.append({"id": f"custom:{holiday_date.isoformat()}", "label": label, "date": holiday_date, "source": "custom"})
    options.sort(key=lambda item: item["date"])
    return options


def combined_holiday_options(start_date_value: date, weeks_to_project_value: int, custom_holidays: list[dict]) -> list[dict]:
    options = []
    seen = set()
    for holiday in holiday_options_for_projection(start_date_value, 52):
        key = f"federal:{holiday['label']}"
        if key in seen:
            continue
        seen.add(key)
        options.append({**holiday, "id": key, "source": "federal"})
    for holiday in custom_holiday_options(custom_holidays):
        key = holiday["id"]
        if key in seen:
            seen.remove(key)
            options = [item for item in options if item["id"] != key]
        options.append(holiday)
    options.sort(key=lambda item: item["date"])
    return options


def federal_holiday_label_for_date(day_value: date) -> str | None:
    for holiday in us_federal_holidays(day_value.year):
        if holiday["date"] == day_value:
            return holiday["label"]
    return None


def resolve_selected_holiday_rules(selected_holiday_values: list[str]) -> tuple[set[str], set[date]]:
    selected_federal_labels = set()
    selected_custom_dates = set()
    for raw_value in selected_holiday_values:
        value = str(raw_value)
        if value.startswith("federal:"):
            selected_federal_labels.add(value.split(":", 1)[1])
            continue
        if value.startswith("custom:"):
            selected_custom_dates.add(date.fromisoformat(value.split(":", 1)[1]))
            continue
        legacy_date = date.fromisoformat(value)
        holiday_label = federal_holiday_label_for_date(legacy_date)
        if holiday_label is not None:
            selected_federal_labels.add(holiday_label)
        else:
            selected_custom_dates.add(legacy_date)
    return selected_federal_labels, selected_custom_dates


def is_off_friday_980(day_value: date, starting_off_friday: date) -> bool:
    if day_value.weekday() != 4:
        return False
    delta_days = (day_value - starting_off_friday).days
    if delta_days % 14 == 0:
        return True
    return False


def scheduled_hours_for_day(day_value: date, work_schedule: dict, selected_holiday_rules: dict) -> float:
    holiday_label = federal_holiday_label_for_date(day_value)
    if holiday_label in selected_holiday_rules["federal_labels"] or day_value in selected_holiday_rules["custom_dates"]:
        return 0.0

    schedule_type = work_schedule["type"]
    weekday = day_value.weekday()

    if schedule_type == "Mon-Fri 8 hours":
        return 8.0 if weekday < 5 else 0.0

    if schedule_type == "9/80":
        if weekday == 5 or weekday == 6:
            return 0.0
        if weekday in (0, 1, 2, 3):
            return 9.0
        if weekday == 4:
            return 0.0 if is_off_friday_980(day_value, work_schedule["starting_off_friday"]) else 8.0

    custom_hours = work_schedule.get("custom_hours", [8.0, 8.0, 8.0, 8.0, 8.0, 0.0, 0.0])
    return float(custom_hours[weekday])


def distribute_hours_by_week(
    start_value: date,
    end_value: date,
    work_schedule: dict,
    selected_holiday_rules: dict,
) -> tuple[float, dict[date, float], int]:
    hours_by_week = {}
    total_hours = 0.0
    working_days = 0
    for day_value in date_range(start_value, end_value):
        scheduled_hours = scheduled_hours_for_day(day_value, work_schedule, selected_holiday_rules)
        if scheduled_hours <= 0:
            continue
        working_days += 1
        total_hours += scheduled_hours
        week_start = monday_of(day_value)
        hours_by_week[week_start] = hours_by_week.get(week_start, 0.0) + scheduled_hours
    return total_hours, hours_by_week, working_days


def normalize_work_schedule_type(value: str) -> str:
    if value in WORK_SCHEDULE_OPTIONS:
        return value
    return "Mon-Fri 8 hours"


def normalize_work_schedule(settings: dict) -> dict:
    schedule_type = normalize_work_schedule_type(str(settings.get("work_schedule_type", "Mon-Fri 8 hours")))
    custom_hours = settings.get("custom_schedule_hours", [8.0, 8.0, 8.0, 8.0, 8.0, 0.0, 0.0])
    if not isinstance(custom_hours, list) or len(custom_hours) != 7:
        custom_hours = [8.0, 8.0, 8.0, 8.0, 8.0, 0.0, 0.0]
    custom_hours = [max(0.0, float(value)) for value in custom_hours]
    starting_off_friday_raw = settings.get("starting_off_friday", date.today().isoformat())
    starting_off_friday = (
        starting_off_friday_raw
        if isinstance(starting_off_friday_raw, date)
        else date.fromisoformat(str(starting_off_friday_raw))
    )
    return {
        "type": schedule_type,
        "custom_hours": custom_hours,
        "starting_off_friday": starting_off_friday,
    }


def build_export_payload(start_date_value: date, pto_day_hours_value: float, weeks_to_project_value: int) -> dict:
    work_schedule = normalize_work_schedule(st.session_state)
    selected_holiday_labels, selected_custom_dates = resolve_selected_holiday_rules(st.session_state.selected_holidays)
    selected_holiday_rules = {
        "federal_labels": selected_holiday_labels,
        "custom_dates": selected_custom_dates,
    }
    return {
        "schema_version": 2,
        "settings": {
            "start_date": start_date_value.isoformat(),
            "pto_day_hours": float(pto_day_hours_value),
            "weeks_to_project": int(weeks_to_project_value),
            "work_schedule_type": work_schedule["type"],
            "custom_schedule_hours": [float(value) for value in work_schedule["custom_hours"]],
            "starting_off_friday": work_schedule["starting_off_friday"].isoformat(),
            "selected_holidays": list(st.session_state.selected_holidays),
            "custom_holidays": [
                {
                    "label": str(item["label"]).strip(),
                    "date": (
                        item["date"].isoformat()
                        if isinstance(item["date"], date)
                        else str(item["date"])
                    ),
                }
                for item in st.session_state.custom_holidays
            ],
        },
        "pto_types": st.session_state.pto_types,
        "planned_time_off": [
            {
                "start_date": entry["start_date"].isoformat(),
                "end_date": entry["end_date"].isoformat(),
                "pto_type": entry["pto_type"],
                "amount_hours": float(display_amount_hours(entry, work_schedule, selected_holiday_rules)),
                "calculation_mode": entry.get("calculation_mode", "range_auto"),
                "reason": entry.get("reason", ""),
            }
            for entry in st.session_state.planned_time_off
        ],
    }


def populate_pto_form(pto_type: dict) -> None:
    st.session_state[PTO_FORM_FIELDS["name"]] = pto_type["name"]
    st.session_state[PTO_FORM_FIELDS["current_balance"]] = float(pto_type["current_balance"])
    st.session_state[PTO_FORM_FIELDS["balance_unit"]] = pto_type["balance_unit"]
    st.session_state[PTO_FORM_FIELDS["accrual_amount"]] = float(pto_type["accrual_amount"])
    st.session_state[PTO_FORM_FIELDS["accrual_unit"]] = pto_type["accrual_unit"]
    st.session_state[PTO_FORM_FIELDS["accrual_frequency"]] = pto_type["accrual_frequency"]
    st.session_state[PTO_FORM_FIELDS["accrual_cap"]] = (
        "" if pto_type.get("accrual_cap") is None else f"{float(pto_type['accrual_cap']):g}"
    )
    st.session_state[PTO_FORM_FIELDS["rollover_limit"]] = (
        "" if pto_type.get("rollover_limit") is None else f"{float(pto_type['rollover_limit']):g}"
    )


def reset_pto_form() -> None:
    st.session_state[PTO_FORM_FIELDS["name"]] = ""
    st.session_state[PTO_FORM_FIELDS["current_balance"]] = 0.0
    st.session_state[PTO_FORM_FIELDS["balance_unit"]] = "hours"
    st.session_state[PTO_FORM_FIELDS["accrual_amount"]] = 0.0
    st.session_state[PTO_FORM_FIELDS["accrual_unit"]] = "hours"
    st.session_state[PTO_FORM_FIELDS["accrual_frequency"]] = "week"
    st.session_state[PTO_FORM_FIELDS["accrual_cap"]] = ""
    st.session_state[PTO_FORM_FIELDS["rollover_limit"]] = ""


def set_edit_selection(name: str | None) -> None:
    st.session_state.editing_pto_name = name
    if name is None:
        reset_pto_form()
        return
    selected_pto = next((item for item in st.session_state.pto_types if item["name"] == name), None)
    if selected_pto is not None:
        populate_pto_form(selected_pto)


def populate_time_off_form(entry: dict) -> None:
    st.session_state[TIME_OFF_FORM_FIELDS["start_date"]] = entry["start_date"]
    st.session_state[TIME_OFF_FORM_FIELDS["end_date"]] = entry["end_date"]
    st.session_state[TIME_OFF_FORM_FIELDS["pto_type"]] = entry["pto_type"]
    st.session_state[TIME_OFF_FORM_FIELDS["reason"]] = entry.get("reason", "")


def reset_time_off_form(default_date: date) -> None:
    st.session_state[TIME_OFF_FORM_FIELDS["start_date"]] = default_date
    st.session_state[TIME_OFF_FORM_FIELDS["end_date"]] = default_date
    st.session_state[TIME_OFF_FORM_FIELDS["pto_type"]] = (
        st.session_state.pto_types[0]["name"] if st.session_state.pto_types else ""
    )
    st.session_state[TIME_OFF_FORM_FIELDS["reason"]] = ""


def set_time_off_edit_selection(index: int | None, default_date: date) -> None:
    st.session_state.editing_time_off_index = index
    if index is None:
        reset_time_off_form(default_date)
        return
    if 0 <= index < len(st.session_state.planned_time_off):
        populate_time_off_form(st.session_state.planned_time_off[index])


def sync_time_off_end_date() -> None:
    start_value = st.session_state[TIME_OFF_FORM_FIELDS["start_date"]]
    end_value = st.session_state[TIME_OFF_FORM_FIELDS["end_date"]]
    if st.session_state.editing_time_off_index is None or end_value < start_value:
        st.session_state[TIME_OFF_FORM_FIELDS["end_date"]] = start_value


def normalize_pto_type_record(item: dict) -> dict:
    required_fields = {
        "name",
        "current_balance",
        "balance_unit",
        "accrual_amount",
        "accrual_unit",
        "accrual_frequency",
    }
    if not isinstance(item, dict) or not required_fields.issubset(item):
        raise ValueError("Each PTO type must include all PTO fields.")

    clean_name = str(item["name"]).strip()
    if not clean_name:
        raise ValueError("PTO type names cannot be blank.")
    balance_unit = item["balance_unit"]
    accrual_unit = item["accrual_unit"]
    accrual_frequency = normalize_accrual_frequency(item["accrual_frequency"])
    if balance_unit not in {"hours", "days"}:
        raise ValueError(f"Invalid balance unit for {clean_name}.")
    if accrual_unit not in {"hours", "days"}:
        raise ValueError(f"Invalid accrual unit for {clean_name}.")
    if accrual_frequency not in FREQUENCY_TO_WEEKS:
        raise ValueError(f"Invalid accrual frequency for {clean_name}.")
    accrual_cap = normalize_optional_limit(item.get("accrual_cap"))
    rollover_limit = normalize_optional_limit(item.get("rollover_limit"))
    return {
        "name": clean_name,
        "current_balance": float(item["current_balance"]),
        "balance_unit": balance_unit,
        "accrual_amount": float(item["accrual_amount"]),
        "accrual_unit": accrual_unit,
        "accrual_frequency": accrual_frequency,
        "accrual_cap": accrual_cap,
        "rollover_limit": rollover_limit,
    }


def normalize_time_off_entry(entry: dict, valid_names: set[str], pto_day_hours_value: float) -> dict:
    if not isinstance(entry, dict):
        raise ValueError("Each planned time off entry must be an object.")

    if {"start_date", "end_date", "pto_type", "amount_hours"}.issubset(entry):
        start_value = date.fromisoformat(str(entry["start_date"]))
        end_value = date.fromisoformat(str(entry["end_date"]))
        pto_type = str(entry["pto_type"]).strip()
        amount_hours = float(entry["amount_hours"])
        reason = str(entry.get("reason", "")).strip()
        if pto_type not in valid_names:
            raise ValueError(f"Planned time off references unknown PTO type: {pto_type}")
        if end_value < start_value:
            raise ValueError("Planned time off end date cannot be before the start date.")
        return {
            "start_date": start_value,
            "end_date": end_value,
            "pto_type": pto_type,
            "amount_hours": amount_hours,
            "calculation_mode": str(entry.get("calculation_mode", "range_auto")),
            "reason": reason,
        }

    if {"date", "pto_type", "amount", "unit"}.issubset(entry):
        single_date = date.fromisoformat(str(entry["date"]))
        pto_type = str(entry["pto_type"]).strip()
        if pto_type not in valid_names:
            raise ValueError(f"Planned time off references unknown PTO type: {pto_type}")
        unit = entry["unit"]
        if unit not in {"hours", "days"}:
            raise ValueError(f"Invalid planned time off unit for {pto_type}.")
        amount_hours = hours_from_value(float(entry["amount"]), unit, pto_day_hours_value)
        return {
            "start_date": single_date,
            "end_date": single_date,
            "pto_type": pto_type,
            "amount_hours": amount_hours,
            "calculation_mode": "legacy_fixed",
            "reason": str(entry.get("reason", "")).strip(),
        }

    raise ValueError("Each planned time off entry must include either the new range fields or the legacy fields.")


def create_time_off_entry(
    start_value: date,
    end_value: date,
    pto_type: str,
    reason: str,
    work_schedule: dict,
    selected_holiday_rules: dict,
) -> tuple[dict, dict]:
    total_hours, hours_by_week, working_days = distribute_hours_by_week(
        start_value,
        end_value,
        work_schedule,
        selected_holiday_rules,
    )
    if end_value < start_value:
        raise ValueError("End date cannot be before the start date.")
    if pto_type.strip() == "":
        raise ValueError("Please choose a PTO type.")
    if total_hours <= 0 or working_days == 0:
        raise ValueError("That date range has no scheduled work hours after weekends, holidays, and off-days are excluded.")
    return {
        "start_date": start_value,
        "end_date": end_value,
        "pto_type": pto_type,
        "amount_hours": total_hours,
        "calculation_mode": "range_auto",
        "reason": reason.strip(),
    }, hours_by_week


def load_import_payload(payload: dict) -> None:
    settings = payload.get("settings", {})
    pto_types = payload.get("pto_types", [])
    planned_time_off = payload.get("planned_time_off", [])

    if not isinstance(settings, dict):
        raise ValueError("Imported settings must be an object.")
    if not isinstance(pto_types, list):
        raise ValueError("Imported PTO types must be a list.")
    if not isinstance(planned_time_off, list):
        raise ValueError("Imported planned time off must be a list.")

    imported_pto_types = []
    seen_names = set()
    for item in pto_types:
        normalized = normalize_pto_type_record(item)
        lowered = normalized["name"].lower()
        if lowered in seen_names:
            raise ValueError(f"Duplicate PTO type found: {normalized['name']}")
        seen_names.add(lowered)
        imported_pto_types.append(normalized)

    start_date_value = date.fromisoformat(str(settings.get("start_date", date.today().isoformat())))
    pto_day_hours_value = float(settings.get("pto_day_hours", settings.get("hours_per_day", 8.0)))
    weeks_to_project_value = int(settings.get("weeks_to_project", 52))
    work_schedule = normalize_work_schedule(settings)
    selected_holidays_raw = settings.get("selected_holidays", [])
    custom_holidays_raw = settings.get("custom_holidays", [])
    if not isinstance(selected_holidays_raw, list):
        raise ValueError("Selected holidays must be a list of ISO date strings.")
    if not isinstance(custom_holidays_raw, list):
        raise ValueError("Custom holidays must be a list.")
    selected_federal_labels, selected_custom_dates = resolve_selected_holiday_rules(selected_holidays_raw)
    custom_holidays = custom_holiday_options(custom_holidays_raw)

    valid_names = {item["name"] for item in imported_pto_types}
    imported_time_off = [
        normalize_time_off_entry(entry, valid_names, pto_day_hours_value)
        for entry in planned_time_off
    ]

    st.session_state.start_date = start_date_value
    st.session_state.pto_day_hours = pto_day_hours_value
    st.session_state.weeks_to_project = weeks_to_project_value
    st.session_state.work_schedule_type = work_schedule["type"]
    st.session_state.custom_schedule_hours = [float(value) for value in work_schedule["custom_hours"]]
    st.session_state.starting_off_friday = work_schedule["starting_off_friday"]
    st.session_state.selected_holidays = sorted(
        [f"federal:{label}" for label in selected_federal_labels]
        + [f"custom:{day.isoformat()}" for day in selected_custom_dates]
    )
    st.session_state.custom_holidays = [
        {"label": item["label"], "date": item["date"].isoformat()}
        for item in custom_holidays
    ]
    st.session_state.pto_types = imported_pto_types
    st.session_state.planned_time_off = imported_time_off
    st.session_state.editing_pto_name = None
    st.session_state.editing_time_off_index = None
    st.session_state.pending_time_off_selector_reset = True
    set_edit_selection(None)
    set_time_off_edit_selection(None, st.session_state.start_date)


def queue_import_payload(payload: dict) -> None:
    st.session_state.pending_import_payload = payload


def build_time_off_usage_by_week(entries: list[dict], work_schedule: dict, selected_holiday_rules: dict) -> dict[tuple[date, str], float]:
    usage_by_week = {}
    for entry in entries:
        if entry.get("calculation_mode") == "legacy_fixed":
            week_start = monday_of(entry["start_date"])
            key = (week_start, entry["pto_type"])
            usage_by_week[key] = usage_by_week.get(key, 0.0) + float(entry["amount_hours"])
            continue
        _, hours_by_week, _ = distribute_hours_by_week(
            entry["start_date"],
            entry["end_date"],
            work_schedule,
            selected_holiday_rules,
        )
        for week_start, amount_hours in hours_by_week.items():
            key = (week_start, entry["pto_type"])
            usage_by_week[key] = usage_by_week.get(key, 0.0) + amount_hours
    return usage_by_week


def display_amount_hours(entry: dict, work_schedule: dict, selected_holiday_rules: dict) -> float:
    if entry.get("calculation_mode") == "legacy_fixed":
        return float(entry["amount_hours"])
    total_hours, _, _ = distribute_hours_by_week(
        entry["start_date"],
        entry["end_date"],
        work_schedule,
        selected_holiday_rules,
    )
    return total_hours


def describe_day_for_entry(day_value: date, work_schedule: dict, selected_holiday_rules: dict) -> tuple[float, str]:
    holiday_label = federal_holiday_label_for_date(day_value)
    if holiday_label in selected_holiday_rules["federal_labels"]:
        return 0.0, f"Holiday off: {holiday_label}"
    if day_value in selected_holiday_rules["custom_dates"]:
        return 0.0, "Custom holiday off"

    if work_schedule["type"] == "Mon-Fri 8 hours":
        if day_value.weekday() >= 5:
            return 0.0, "Weekend"
        return 8.0, "Scheduled workday"

    if work_schedule["type"] == "9/80":
        if day_value.weekday() >= 5:
            return 0.0, "Weekend"
        if day_value.weekday() in (0, 1, 2, 3):
            return 9.0, "Scheduled 9/80 workday"
        if is_off_friday_980(day_value, work_schedule["starting_off_friday"]):
            return 0.0, "Off Friday"
        return 8.0, "On Friday"

    custom_hours = float(work_schedule.get("custom_hours", [8.0, 8.0, 8.0, 8.0, 8.0, 0.0, 0.0])[day_value.weekday()])
    if custom_hours <= 0:
        return 0.0, "Not scheduled"
    return custom_hours, "Scheduled custom workday"


def build_entry_detail_rows(entry: dict, work_schedule: dict, selected_holiday_rules: dict, pto_day_hours_value: float) -> list[dict]:
    if entry.get("calculation_mode") == "legacy_fixed":
        amount_hours = float(entry["amount_hours"])
        return [{
            "Date": entry["start_date"].isoformat(),
            "Day": entry["start_date"].strftime("%A"),
            "Hours Used": round(amount_hours, 2),
            "Days Used": round(days_from_hours(amount_hours, pto_day_hours_value), 2),
            "Detail": "Legacy fixed PTO amount",
        }]

    rows = []
    for day_value in date_range(entry["start_date"], entry["end_date"]):
        used_hours, detail = describe_day_for_entry(day_value, work_schedule, selected_holiday_rules)
        rows.append({
            "Date": day_value.isoformat(),
            "Day": day_value.strftime("%A"),
            "Hours Used": round(used_hours, 2),
            "Days Used": round(days_from_hours(used_hours, pto_day_hours_value), 2),
            "Detail": detail,
        })
    return rows


def refresh_planned_time_off(entries: list[dict], work_schedule: dict, selected_holiday_rules: dict) -> list[dict]:
    refreshed_entries = []
    for entry in entries:
        updated_entry = dict(entry)
        if updated_entry.get("calculation_mode") != "legacy_fixed":
            updated_entry["amount_hours"] = display_amount_hours(updated_entry, work_schedule, selected_holiday_rules)
        refreshed_entries.append(updated_entry)
    return refreshed_entries


def build_warning_rows(projection_df: pd.DataFrame, pto_types: list[dict], pto_day_hours_value: float) -> list[dict]:
    rows = []
    for item in pto_types:
        column_name = f"{item['name']} Balance (hrs)"
        less_than_day_week = None
        negative_week = None
        for _, row in projection_df.iterrows():
            balance = float(row[column_name])
            week_start = row["Week Start"]
            if less_than_day_week is None and 0 <= balance < pto_day_hours_value:
                less_than_day_week = week_start
            if negative_week is None and balance < 0:
                negative_week = week_start
            if less_than_day_week is not None and negative_week is not None:
                break
        if less_than_day_week is not None or negative_week is not None:
            rows.append({
                "PTO Type": item["name"],
                "Below 1 PTO day": less_than_day_week.isoformat() if less_than_day_week is not None else "-",
                "Below zero": negative_week.isoformat() if negative_week is not None else "-",
            })
    return rows


if "pto_types" not in st.session_state:
    st.session_state.pto_types = []
if "planned_time_off" not in st.session_state:
    st.session_state.planned_time_off = []
if "start_date" not in st.session_state:
    st.session_state.start_date = date.today()
if "pto_day_hours" not in st.session_state:
    st.session_state.pto_day_hours = 8.0
if "weeks_to_project" not in st.session_state:
    st.session_state.weeks_to_project = 52
if "work_schedule_type" not in st.session_state:
    st.session_state.work_schedule_type = "Mon-Fri 8 hours"
if "custom_schedule_hours" not in st.session_state:
    st.session_state.custom_schedule_hours = [8.0, 8.0, 8.0, 8.0, 8.0, 0.0, 0.0]
if "starting_off_friday" not in st.session_state:
    st.session_state.starting_off_friday = date.today()
if "selected_holidays" not in st.session_state:
    st.session_state.selected_holidays = []
if "custom_holidays" not in st.session_state:
    st.session_state.custom_holidays = []
if "new_holiday_label" not in st.session_state:
    st.session_state.new_holiday_label = ""
if "new_holiday_date" not in st.session_state:
    st.session_state.new_holiday_date = date.today()
if "editing_pto_name" not in st.session_state:
    st.session_state.editing_pto_name = None
if "pto_edit_selector" not in st.session_state:
    st.session_state.pto_edit_selector = "Add new PTO type"
if "editing_time_off_index" not in st.session_state:
    st.session_state.editing_time_off_index = None
if "time_off_edit_selector" not in st.session_state:
    st.session_state.time_off_edit_selector = "Add new planned time off"
if "expanded_time_off_details" not in st.session_state:
    st.session_state.expanded_time_off_details = None
if "pending_import_payload" in st.session_state:
    payload_to_import = st.session_state.pop("pending_import_payload")
    load_import_payload(payload_to_import)
if "pending_time_off_selector_reset" not in st.session_state:
    st.session_state.pending_time_off_selector_reset = False
if "pending_holiday_form_reset" not in st.session_state:
    st.session_state.pending_holiday_form_reset = False

if st.session_state.pending_holiday_form_reset:
    st.session_state.new_holiday_label = ""
    st.session_state.new_holiday_date = date.today()
    st.session_state.pending_holiday_form_reset = False

for idx, item in enumerate(list(st.session_state.pto_types)):
    st.session_state.pto_types[idx] = normalize_pto_type_record(item)
for session_key in PTO_FORM_FIELDS.values():
    if session_key not in st.session_state:
        reset_pto_form()
        break
st.session_state[PTO_FORM_FIELDS["accrual_frequency"]] = normalize_accrual_frequency(
    st.session_state[PTO_FORM_FIELDS["accrual_frequency"]]
)
for session_key in TIME_OFF_FORM_FIELDS.values():
    if session_key not in st.session_state:
        reset_time_off_form(st.session_state.start_date)
        break

st.title("PTO Calculator")
st.caption("Track weekly PTO balances and account for your real work schedule.")
st.markdown(
    """
    <style>
    :root {
        --pto-expander-bg-light: #edf1f5;
        --pto-expander-summary-light: #e2e8f0;
        --pto-expander-border-light: #cbd5e1;
        --pto-expander-bg-dark: #2f3338;
        --pto-expander-summary-dark: #3a4047;
        --pto-expander-border-dark: #4b5563;
    }
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #c62828;
        border-color: #c62828;
        color: white;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background-color: #b71c1c;
        border-color: #b71c1c;
        color: white;
    }
    div[data-testid="stExpander"] {
        border: 1px solid var(--pto-expander-border-light);
        border-radius: 12px;
        background: var(--pto-expander-bg-light);
        margin-bottom: 0.9rem;
        overflow: hidden;
    }
    div[data-testid="stExpander"] details {
        background: var(--pto-expander-bg-light);
    }
    div[data-testid="stExpander"] details summary {
        background: var(--pto-expander-summary-light);
    }
    @media (prefers-color-scheme: dark) {
        div[data-testid="stExpander"] {
            border: 1px solid var(--pto-expander-border-dark);
            background: var(--pto-expander-bg-dark);
        }
        div[data-testid="stExpander"] details {
            background: var(--pto-expander-bg-dark);
        }
        div[data-testid="stExpander"] details summary {
            background: var(--pto-expander-summary-dark);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    with st.expander("Settings", expanded=True):
        start_date = st.date_input("Projection start date", key="start_date")
        pto_day_hours = st.number_input("PTO day hours", min_value=1.0, max_value=24.0, step=0.5, key="pto_day_hours")
        weeks_to_project = st.slider("Weeks to project", min_value=4, max_value=104, step=4, key="weeks_to_project")

    with st.expander("Work Schedule", expanded=False):
        work_schedule_type = st.selectbox("Schedule", WORK_SCHEDULE_OPTIONS, key="work_schedule_type")
        if work_schedule_type == "9/80":
            st.date_input("Starting off Friday", key="starting_off_friday")
            st.caption("Every other Friday is treated as off starting from this date.")
            if st.session_state.starting_off_friday.weekday() != 4:
                st.warning("Starting off Friday should be a Friday so the 9/80 pattern lines up correctly.")
        elif work_schedule_type == "Custom":
            custom_cols = st.columns(2)
            updated_custom_hours = []
            for index, weekday_name in enumerate(WEEKDAY_NAMES):
                column = custom_cols[index % 2]
                updated_custom_hours.append(
                    column.number_input(
                        weekday_name,
                        min_value=0.0,
                        max_value=24.0,
                        step=0.5,
                        value=float(st.session_state.custom_schedule_hours[index]),
                        key=f"custom_schedule_hour_{index}",
                    )
                )
            st.session_state.custom_schedule_hours = updated_custom_hours

    holiday_options = combined_holiday_options(start_date, weeks_to_project, st.session_state.custom_holidays)
    with st.expander("Holidays", expanded=False):
        st.caption("Checked holidays are treated as days off.")
        updated_selected = []
        for holiday in holiday_options:
            holiday_id = holiday["id"]
            default_checked = holiday_id in st.session_state.selected_holidays
            source_label = "Custom" if holiday.get("source") == "custom" else "Federal"
            checked = st.checkbox(
                f"{holiday['date'].isoformat()} - {holiday['label']} ({source_label})",
                value=default_checked,
                key=f"holiday_checkbox_{holiday_id}",
            )
            if checked:
                updated_selected.append(holiday_id)
        st.session_state.selected_holidays = updated_selected

        st.markdown("**Add custom holiday**")
        st.text_input("Holiday name", key="new_holiday_label", placeholder="Company shutdown day")
        st.date_input("Holiday date", key="new_holiday_date")
        if st.button("Add holiday"):
            label = st.session_state.new_holiday_label.strip()
            holiday_id = st.session_state.new_holiday_date.isoformat()
            if not label:
                st.warning("Please enter a holiday name.")
            else:
                st.session_state.custom_holidays = [
                    item
                    for item in st.session_state.custom_holidays
                    if str(item["date"]) != holiday_id
                ]
                st.session_state.custom_holidays.append({
                    "label": label,
                    "date": holiday_id,
                })
                custom_key = f"custom:{holiday_id}"
                if custom_key not in st.session_state.selected_holidays:
                    st.session_state.selected_holidays.append(custom_key)
                st.session_state.pending_holiday_form_reset = True
                st.rerun()

    with st.expander("Import / Export", expanded=False):
        st.caption(
            "Exports include projection settings, PTO day hours, work schedule, starting off Friday, selected holidays, custom holidays, PTO types, and planned PTO."
        )
        export_payload = build_export_payload(start_date, pto_day_hours, weeks_to_project)
        export_json = json.dumps(export_payload, indent=2).encode("utf-8")
        st.download_button(
            "Export all data",
            data=export_json,
            file_name="pto_calculator_data.json",
            mime="application/json",
        )

        uploaded_file = st.file_uploader("Import saved data", type=["json"])
        if uploaded_file is not None and st.button("Import data and replace current session"):
            try:
                queue_import_payload(json.load(uploaded_file))
            except Exception as exc:
                st.error(f"Import failed: {exc}")
            else:
                st.rerun()

work_schedule = normalize_work_schedule(st.session_state)
selected_federal_labels, selected_custom_dates = resolve_selected_holiday_rules(st.session_state.selected_holidays)
selected_holiday_rules = {
    "federal_labels": selected_federal_labels,
    "custom_dates": selected_custom_dates,
}

with st.expander("PTO Types", expanded=True):
    pto_manage_options = ["Add new PTO type"] + [item["name"] for item in st.session_state.pto_types]
    if st.session_state.pto_edit_selector not in pto_manage_options:
        st.session_state.pto_edit_selector = "Add new PTO type"
    selected_manage_option = st.selectbox(
        "Choose a PTO type to add or edit",
        options=pto_manage_options,
        key="pto_edit_selector",
    )
    target_edit_name = None if selected_manage_option == "Add new PTO type" else selected_manage_option
    if st.session_state.editing_pto_name != target_edit_name:
        set_edit_selection(target_edit_name)

    with st.form("pto_type_form"):
        c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 1, 1, 1, 1])
        name = c1.text_input("Type name", placeholder="PTO, Sick, Personal...", key=PTO_FORM_FIELDS["name"])
        current_balance = c2.number_input(
            "Current balance",
            min_value=0.0,
            step=1.0,
            key=PTO_FORM_FIELDS["current_balance"],
        )
        balance_unit = c3.selectbox("Balance unit", ["hours", "days"], key=PTO_FORM_FIELDS["balance_unit"])
        accrual_amount = c4.number_input(
            "Accrual amount",
            min_value=0.0,
            step=0.25,
            key=PTO_FORM_FIELDS["accrual_amount"],
        )
        accrual_unit = c5.selectbox("Accrual unit", ["hours", "days"], key=PTO_FORM_FIELDS["accrual_unit"])
        accrual_frequency = c6.selectbox(
            "Frequency",
            ["week", "every 2 weeks", "twice a month", "month", "year"],
            key=PTO_FORM_FIELDS["accrual_frequency"],
        )
        c7, c8 = st.columns(2)
        accrual_cap = c7.text_input(
            f"Accrual cap ({balance_unit}, blank = none)",
            key=PTO_FORM_FIELDS["accrual_cap"],
        )
        rollover_limit = c8.text_input(
            f"Rollover limit ({balance_unit}, blank = unlimited)",
            key=PTO_FORM_FIELDS["rollover_limit"],
        )

        form_action = "Add PTO type" if st.session_state.editing_pto_name is None else "Save PTO changes"
        submitted = st.form_submit_button(form_action)
        if submitted:
            clean_name = name.strip()
            existing_names = {
                item["name"].lower()
                for item in st.session_state.pto_types
                if item["name"] != st.session_state.editing_pto_name
            }
            if not clean_name:
                st.warning("Please enter a PTO type name.")
            elif clean_name.lower() in existing_names:
                st.warning("That PTO type already exists.")
            else:
                try:
                    normalized_record = normalize_pto_type_record({
                        "name": clean_name,
                        "current_balance": float(current_balance),
                        "balance_unit": balance_unit,
                        "accrual_amount": float(accrual_amount),
                        "accrual_unit": accrual_unit,
                        "accrual_frequency": accrual_frequency,
                        "accrual_cap": accrual_cap,
                        "rollover_limit": rollover_limit,
                    })
                except Exception as exc:
                    st.warning(str(exc))
                else:
                    if st.session_state.editing_pto_name is None:
                        st.session_state.pto_types.append(normalized_record)
                        st.session_state.editing_pto_name = clean_name
                        st.rerun()
                    else:
                        original_name = st.session_state.editing_pto_name
                        for item in st.session_state.pto_types:
                            if item["name"] == original_name:
                                item.update(normalized_record)
                                break
                        for entry in st.session_state.planned_time_off:
                            if entry["pto_type"] == original_name:
                                entry["pto_type"] = clean_name
                        st.session_state.editing_pto_name = clean_name
                        st.rerun()

    if st.session_state.editing_pto_name is not None and st.button("Delete selected PTO type"):
        deleted_name = st.session_state.editing_pto_name
        st.session_state.pto_types = [item for item in st.session_state.pto_types if item["name"] != deleted_name]
        st.session_state.planned_time_off = [
            entry for entry in st.session_state.planned_time_off if entry["pto_type"] != deleted_name
        ]
        st.session_state.editing_pto_name = None
        st.rerun()

    if st.session_state.pto_types:
        pto_df = pd.DataFrame([
            {
                "name": item["name"],
                "current_balance": item["current_balance"],
                "balance_unit": item["balance_unit"],
                "accrual_amount": item["accrual_amount"],
                "accrual_unit": item["accrual_unit"],
                "accrual_frequency": item["accrual_frequency"],
                "accrual_cap": item.get("accrual_cap"),
                "rollover_limit": item.get("rollover_limit"),
            }
            for item in st.session_state.pto_types
        ])
        st.dataframe(pto_df, use_container_width=True, hide_index=True)
    else:
        st.info("Add at least one PTO type to start projecting balances.")

with st.expander("Planned Time Off", expanded=True):
    if st.session_state.pto_types:
        if st.session_state.pending_time_off_selector_reset:
            st.session_state.time_off_edit_selector = "Add new planned time off"
            st.session_state.pending_time_off_selector_reset = False

        valid_pto_names = [item["name"] for item in st.session_state.pto_types]
        if st.session_state.get(TIME_OFF_FORM_FIELDS["pto_type"]) not in valid_pto_names:
            st.session_state[TIME_OFF_FORM_FIELDS["pto_type"]] = valid_pto_names[0]

        time_off_options = ["Add new planned time off"] + [
            (
                f"{i}: {entry['start_date']} to {entry['end_date']} | {entry['pto_type']} | "
                f"{display_amount_hours(entry, work_schedule, selected_holiday_rules):.2f} hrs"
                + (f" | {entry.get('reason', '').strip()}" if entry.get("reason", "").strip() else "")
            )
            for i, entry in enumerate(st.session_state.planned_time_off)
        ]
        if st.session_state.time_off_edit_selector not in time_off_options:
            st.session_state.time_off_edit_selector = "Add new planned time off"
        selected_time_off_option = st.selectbox(
            "Choose a planned time off entry to add or edit",
            options=time_off_options,
            key="time_off_edit_selector",
        )
        target_time_off_index = (
            None if selected_time_off_option == "Add new planned time off" else int(selected_time_off_option.split(":", 1)[0])
        )
        if st.session_state.editing_time_off_index != target_time_off_index:
            set_time_off_edit_selection(target_time_off_index, start_date)

        preview_total_hours = 0.0
        preview_working_days = 0
        preview_error = None
        try:
            preview_total_hours, _, preview_working_days = distribute_hours_by_week(
                st.session_state[TIME_OFF_FORM_FIELDS["start_date"]],
                st.session_state[TIME_OFF_FORM_FIELDS["end_date"]],
                work_schedule,
                selected_holiday_rules,
            )
        except Exception as exc:
            preview_error = str(exc)

        d1, d2, d3 = st.columns([1.1, 1.1, 1.2])
        d1.date_input("Start date", key=TIME_OFF_FORM_FIELDS["start_date"], on_change=sync_time_off_end_date)
        d2.date_input("End date", key=TIME_OFF_FORM_FIELDS["end_date"])
        d3.selectbox(
            "PTO type",
            [x["name"] for x in st.session_state.pto_types],
            key=TIME_OFF_FORM_FIELDS["pto_type"],
        )
        reason = st.text_input(
            "Reason (optional)",
            placeholder="Vacation, doctor's appointment, holiday travel...",
            key=TIME_OFF_FORM_FIELDS["reason"],
        )

        if preview_error is None:
            st.caption(
                f"Calculated usage: {preview_total_hours:.2f} hrs "
                f"({days_from_hours(preview_total_hours, pto_day_hours):.2f} days) across {preview_working_days} workday(s)."
            )

        time_off_action = "Add planned time off" if st.session_state.editing_time_off_index is None else "Save time off changes"
        if st.button(time_off_action):
            try:
                entry_data, _ = create_time_off_entry(
                    st.session_state[TIME_OFF_FORM_FIELDS["start_date"]],
                    st.session_state[TIME_OFF_FORM_FIELDS["end_date"]],
                    st.session_state[TIME_OFF_FORM_FIELDS["pto_type"]],
                    reason,
                    work_schedule,
                    selected_holiday_rules,
                )
            except Exception as exc:
                st.warning(str(exc))
            else:
                if st.session_state.editing_time_off_index is None:
                    st.session_state.planned_time_off.append(entry_data)
                else:
                    st.session_state.planned_time_off[st.session_state.editing_time_off_index] = entry_data
                st.session_state.editing_time_off_index = None
                st.session_state.pending_time_off_selector_reset = True
                st.rerun()

        if st.session_state.editing_time_off_index is not None and st.button("Delete selected planned time off"):
            st.session_state.planned_time_off.pop(st.session_state.editing_time_off_index)
            st.session_state.editing_time_off_index = None
            st.session_state.pending_time_off_selector_reset = True
            st.rerun()

        if st.session_state.planned_time_off:
            st.markdown("### Planned PTO Entries")
            header_cols = st.columns([0.45, 1.0, 1.0, 1.1, 0.8, 0.8, 1.8, 0.5])
            header_cols[0].markdown("** **")
            header_cols[1].markdown("**Start**")
            header_cols[2].markdown("**End**")
            header_cols[3].markdown("**PTO Type**")
            header_cols[4].markdown("**Hours**")
            header_cols[5].markdown("**Days**")
            header_cols[6].markdown("**Reason**")
            header_cols[7].markdown("**Delete**")

            sorted_entries = sorted(
                enumerate(st.session_state.planned_time_off),
                key=lambda item: (item[1]["start_date"], item[1]["end_date"]),
            )
            for original_index, entry in sorted_entries:
                amount_hours = display_amount_hours(entry, work_schedule, selected_holiday_rules)
                row_cols = st.columns([0.45, 1.0, 1.0, 1.1, 0.8, 0.8, 1.8, 0.5])
                is_expanded = st.session_state.expanded_time_off_details == original_index
                toggle_label = "▾" if is_expanded else "▸"
                if row_cols[0].button(toggle_label, key=f"toggle_planned_pto_{original_index}"):
                    st.session_state.expanded_time_off_details = None if is_expanded else original_index
                    st.rerun()
                row_cols[1].write(str(entry["start_date"]))
                row_cols[2].write(str(entry["end_date"]))
                row_cols[3].write(entry["pto_type"])
                row_cols[4].write(f"{amount_hours:.2f}")
                row_cols[5].write(f"{days_from_hours(amount_hours, pto_day_hours):.2f}")
                row_cols[6].write(entry.get("reason", "").strip() or "-")
                if row_cols[7].button("🗑", key=f"delete_planned_pto_{original_index}", type="primary"):
                    st.session_state.planned_time_off.pop(original_index)
                    if st.session_state.editing_time_off_index == original_index:
                        st.session_state.editing_time_off_index = None
                    elif (
                        st.session_state.editing_time_off_index is not None
                        and st.session_state.editing_time_off_index > original_index
                    ):
                        st.session_state.editing_time_off_index -= 1
                    if st.session_state.expanded_time_off_details == original_index:
                        st.session_state.expanded_time_off_details = None
                    elif (
                        st.session_state.expanded_time_off_details is not None
                        and st.session_state.expanded_time_off_details > original_index
                    ):
                        st.session_state.expanded_time_off_details -= 1
                    st.session_state.pending_time_off_selector_reset = True
                    st.rerun()
                if is_expanded:
                    detail_rows = build_entry_detail_rows(entry, work_schedule, selected_holiday_rules, pto_day_hours)
                    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Add at least one PTO type to create planned time off entries.")

with st.expander("Weekly Balance Projection", expanded=True):
    if st.session_state.pto_types:
        balances = {
            item["name"]: hours_from_value(item["current_balance"], item["balance_unit"], pto_day_hours)
            for item in st.session_state.pto_types
        }
        caps = {
            item["name"]: limit_hours(item.get("accrual_cap"), item["balance_unit"], pto_day_hours)
            for item in st.session_state.pto_types
        }
        rollover_limits = {
            item["name"]: limit_hours(item.get("rollover_limit"), item["balance_unit"], pto_day_hours)
            for item in st.session_state.pto_types
        }
        time_off_by_week = build_time_off_usage_by_week(
            st.session_state.planned_time_off,
            work_schedule,
            selected_holiday_rules,
        )
        projection_start = monday_of(start_date)
        per_week_accrual = {
            item["name"]: accrual_hours_per_week(
                item["accrual_amount"],
                item["accrual_unit"],
                item["accrual_frequency"],
                pto_day_hours,
            )
            for item in st.session_state.pto_types
        }

        rows = []
        for week_num in range(weeks_to_project):
            week_start = projection_start + timedelta(weeks=week_num)
            week_end = week_start + timedelta(days=6)
            row = {
                "Week #": week_num + 1,
                "Week Start": week_start,
                "Week End": week_end,
            }
            for item in st.session_state.pto_types:
                name = item["name"]
                accrued = per_week_accrual[name]
                cap_hours = caps[name]
                if cap_hours is not None:
                    accrued = max(0.0, min(accrued, cap_hours - balances[name]))
                used = time_off_by_week.get((week_start, name), 0.0)
                balances[name] += accrued
                balances[name] -= used
                rollover_trim = 0.0
                rollover_limit_hours = rollover_limits[name]
                if week_end.year != week_start.year and rollover_limit_hours is not None:
                    trimmed_balance = min(balances[name], rollover_limit_hours)
                    rollover_trim = max(0.0, balances[name] - trimmed_balance)
                    balances[name] = trimmed_balance
                row[f"{name} Accrued (hrs)"] = round(accrued, 2)
                row[f"{name} Used (hrs)"] = round(used, 2)
                row[f"{name} Rollover Trim (hrs)"] = round(rollover_trim, 2)
                row[f"{name} Balance (hrs)"] = round(balances[name], 2)
                row[f"{name} Balance (days)"] = round(days_from_hours(balances[name], pto_day_hours), 2)
            rows.append(row)

        projection_df = pd.DataFrame(rows)
        warning_rows = build_warning_rows(projection_df, st.session_state.pto_types, pto_day_hours)
        if warning_rows:
            st.markdown("### Warning summary")
            st.dataframe(pd.DataFrame(warning_rows), use_container_width=True, hide_index=True)

        st.caption(f"Balances in {weeks_to_project} weeks given planned PTO.")
        metric_cols = st.columns(len(st.session_state.pto_types))
        for col, item in zip(metric_cols, st.session_state.pto_types):
            final_hrs = float(projection_df.iloc[-1][f"{item['name']} Balance (hrs)"])
            final_days = float(projection_df.iloc[-1][f"{item['name']} Balance (days)"])
            col.metric(item["name"], f"{final_hrs:.2f} hrs", f"{final_days:.2f} days")

        st.dataframe(projection_df, use_container_width=True, hide_index=True)
        st.line_chart(
            projection_df.set_index("Week Start")[[f"{item['name']} Balance (hrs)" for item in st.session_state.pto_types]],
            use_container_width=True,
        )

        csv = projection_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download projection as CSV", data=csv, file_name="pto_projection.csv", mime="text/csv")

        st.markdown("### Notes")
        st.markdown(
            "- PTO balances and accruals entered in **days** are converted using **PTO day hours**.\n"
            "- Planned time off ranges auto-calculate from your work schedule and skip selected holidays.\n"
            "- The default schedule ignores weekends, the 9/80 schedule skips alternating off-Fridays, and custom schedules use your weekday hour settings.\n"
            "- Accrual caps stop additional accrual once a PTO bank reaches its cap, and rollover limits trim balances at the year boundary.\n"
            "- Warning summary rows show the first week a PTO type dips below one PTO day and the first week it goes negative."
        )
    else:
        st.info("Once you add PTO types, your weekly projection will appear here.")
