import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="PTO Calculator", layout="wide")

UNIT_TO_HOURS = {
    "hours": 1.0,
    "days": 8.0,
}
FREQUENCY_TO_WEEKS = {
    "week": 1.0,
    "every 2 weeks": 2.0,
    "twice a month": 52.0 / 24.0,
    "month": 52.0 / 12.0,
    "year": 52.0,
}
PTO_FORM_FIELDS = {
    "name": "pto_form_name",
    "current_balance": "pto_form_current_balance",
    "balance_unit": "pto_form_balance_unit",
    "accrual_amount": "pto_form_accrual_amount",
    "accrual_unit": "pto_form_accrual_unit",
    "accrual_frequency": "pto_form_accrual_frequency",
}
TIME_OFF_FORM_FIELDS = {
    "date": "time_off_form_date",
    "pto_type": "time_off_form_pto_type",
    "amount": "time_off_form_amount",
    "unit": "time_off_form_unit",
    "reason": "time_off_form_reason",
}


def accrual_hours_per_week(amount: float, unit: str, frequency: str) -> float:
    hours = amount * UNIT_TO_HOURS[unit]
    return hours / FREQUENCY_TO_WEEKS[frequency]


def normalize_accrual_frequency(frequency: str) -> str:
    legacy_frequency_map = {
        "bi-weekly": "every 2 weeks",
    }
    return legacy_frequency_map.get(frequency, frequency)


def build_export_payload(start_date_value: date, hours_per_day_value: float, weeks_to_project_value: int) -> dict:
    return {
        "settings": {
            "start_date": start_date_value.isoformat(),
            "hours_per_day": float(hours_per_day_value),
            "weeks_to_project": int(weeks_to_project_value),
        },
        "pto_types": st.session_state.pto_types,
        "planned_time_off": [
            {
                **entry,
                "date": entry["date"].isoformat(),
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


def reset_pto_form() -> None:
    st.session_state[PTO_FORM_FIELDS["name"]] = ""
    st.session_state[PTO_FORM_FIELDS["current_balance"]] = 0.0
    st.session_state[PTO_FORM_FIELDS["balance_unit"]] = "hours"
    st.session_state[PTO_FORM_FIELDS["accrual_amount"]] = 0.0
    st.session_state[PTO_FORM_FIELDS["accrual_unit"]] = "hours"
    st.session_state[PTO_FORM_FIELDS["accrual_frequency"]] = "week"


def set_edit_selection(name: str | None) -> None:
    st.session_state.editing_pto_name = name
    if name is None:
        reset_pto_form()
        return

    selected_pto = next((item for item in st.session_state.pto_types if item["name"] == name), None)
    if selected_pto is not None:
        populate_pto_form(selected_pto)


def populate_time_off_form(entry: dict) -> None:
    st.session_state[TIME_OFF_FORM_FIELDS["date"]] = entry["date"]
    st.session_state[TIME_OFF_FORM_FIELDS["pto_type"]] = entry["pto_type"]
    st.session_state[TIME_OFF_FORM_FIELDS["amount"]] = float(entry["amount"])
    st.session_state[TIME_OFF_FORM_FIELDS["unit"]] = entry["unit"]
    st.session_state[TIME_OFF_FORM_FIELDS["reason"]] = entry.get("reason", "")


def reset_time_off_form(default_date: date) -> None:
    st.session_state[TIME_OFF_FORM_FIELDS["date"]] = default_date
    st.session_state[TIME_OFF_FORM_FIELDS["pto_type"]] = (
        st.session_state.pto_types[0]["name"] if st.session_state.pto_types else ""
    )
    st.session_state[TIME_OFF_FORM_FIELDS["amount"]] = 1.0
    st.session_state[TIME_OFF_FORM_FIELDS["unit"]] = "days"
    st.session_state[TIME_OFF_FORM_FIELDS["reason"]] = ""


def set_time_off_edit_selection(index: int | None, default_date: date) -> None:
    st.session_state.editing_time_off_index = index
    if index is None:
        reset_time_off_form(default_date)
        return

    if 0 <= index < len(st.session_state.planned_time_off):
        populate_time_off_form(st.session_state.planned_time_off[index])


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

    required_pto_fields = {
        "name",
        "current_balance",
        "balance_unit",
        "accrual_amount",
        "accrual_unit",
        "accrual_frequency",
    }
    imported_pto_types = []
    seen_names = set()
    for item in pto_types:
        if not isinstance(item, dict) or not required_pto_fields.issubset(item):
            raise ValueError("Each PTO type must include all PTO fields.")

        clean_name = str(item["name"]).strip()
        if not clean_name:
            raise ValueError("PTO type names cannot be blank.")
        normalized_name = clean_name.lower()
        if normalized_name in seen_names:
            raise ValueError(f"Duplicate PTO type found: {clean_name}")
        seen_names.add(normalized_name)

        balance_unit = item["balance_unit"]
        accrual_unit = item["accrual_unit"]
        accrual_frequency = normalize_accrual_frequency(item["accrual_frequency"])
        if balance_unit not in UNIT_TO_HOURS:
            raise ValueError(f"Invalid balance unit for {clean_name}.")
        if accrual_unit not in UNIT_TO_HOURS:
            raise ValueError(f"Invalid accrual unit for {clean_name}.")
        if accrual_frequency not in FREQUENCY_TO_WEEKS:
            raise ValueError(f"Invalid accrual frequency for {clean_name}.")

        imported_pto_types.append({
            "name": clean_name,
            "current_balance": float(item["current_balance"]),
            "balance_unit": balance_unit,
            "accrual_amount": float(item["accrual_amount"]),
            "accrual_unit": accrual_unit,
            "accrual_frequency": accrual_frequency,
        })

    imported_time_off = []
    valid_names = {item["name"] for item in imported_pto_types}
    for entry in planned_time_off:
        if not isinstance(entry, dict):
            raise ValueError("Each planned time off entry must be an object.")
        if not {"date", "pto_type", "amount", "unit"}.issubset(entry):
            raise ValueError("Each planned time off entry must include date, PTO type, amount, and unit.")

        entry_date = date.fromisoformat(str(entry["date"]))
        pto_type = str(entry["pto_type"]).strip()
        unit = entry["unit"]
        if pto_type not in valid_names:
            raise ValueError(f"Planned time off references unknown PTO type: {pto_type}")
        if unit not in UNIT_TO_HOURS:
            raise ValueError(f"Invalid planned time off unit for {pto_type}.")

        imported_time_off.append({
            "date": entry_date,
            "pto_type": pto_type,
            "amount": float(entry["amount"]),
            "unit": unit,
            "reason": str(entry.get("reason", "")).strip(),
        })

    st.session_state.start_date = date.fromisoformat(str(settings.get("start_date", date.today().isoformat())))
    st.session_state.hours_per_day = float(settings.get("hours_per_day", 8.0))
    st.session_state.weeks_to_project = int(settings.get("weeks_to_project", 52))
    st.session_state.pto_types = imported_pto_types
    st.session_state.planned_time_off = imported_time_off
    st.session_state.confirm_delete_time_off_index = None
    set_edit_selection(None)
    set_time_off_edit_selection(None, st.session_state.start_date)


def queue_import_payload(payload: dict) -> None:
    st.session_state.pending_import_payload = payload


if "pto_types" not in st.session_state:
    st.session_state.pto_types = []
if "planned_time_off" not in st.session_state:
    st.session_state.planned_time_off = []
if "start_date" not in st.session_state:
    st.session_state.start_date = date.today()
if "hours_per_day" not in st.session_state:
    st.session_state.hours_per_day = 8.0
if "weeks_to_project" not in st.session_state:
    st.session_state.weeks_to_project = 52
if "editing_pto_name" not in st.session_state:
    st.session_state.editing_pto_name = None
if "pto_edit_selector" not in st.session_state:
    st.session_state.pto_edit_selector = "Add new PTO type"
if "editing_time_off_index" not in st.session_state:
    st.session_state.editing_time_off_index = None
if "time_off_edit_selector" not in st.session_state:
    st.session_state.time_off_edit_selector = "Add new planned time off"
if "confirm_delete_time_off_index" not in st.session_state:
    st.session_state.confirm_delete_time_off_index = None
if "pending_import_payload" in st.session_state:
    payload_to_import = st.session_state.pop("pending_import_payload")
    load_import_payload(payload_to_import)
for item in st.session_state.pto_types:
    item["accrual_frequency"] = normalize_accrual_frequency(item["accrual_frequency"])
for field_key, session_key in PTO_FORM_FIELDS.items():
    if session_key not in st.session_state:
        reset_pto_form()
        break
st.session_state[PTO_FORM_FIELDS["accrual_frequency"]] = normalize_accrual_frequency(
    st.session_state[PTO_FORM_FIELDS["accrual_frequency"]]
)
for field_key, session_key in TIME_OFF_FORM_FIELDS.items():
    if session_key not in st.session_state:
        reset_time_off_form(st.session_state.start_date)
        break


st.title("PTO Calculator")
st.caption("Track weekly PTO balances for the next 52 weeks across multiple leave types.")
st.markdown(
    """
    <style>
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
    div[data-testid="stButton"] button[data-testid="baseButton-secondary"][aria-label="Reset pending delete"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Settings")
    start_date = st.date_input("Projection start date", key="start_date")
    hours_per_day = st.number_input("Hours per day", min_value=1.0, max_value=24.0, step=0.5, key="hours_per_day")
    weeks_to_project = st.slider("Weeks to project", min_value=4, max_value=104, step=4, key="weeks_to_project")

    st.divider()
    st.subheader("Import / Export")
    export_payload = build_export_payload(start_date, hours_per_day, weeks_to_project)
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
            payload = json.load(uploaded_file)
            queue_import_payload(payload)
        except Exception as exc:
            st.error(f"Import failed: {exc}")
        else:
            st.rerun()

st.subheader("1) Add or edit PTO types")

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
    name = c1.text_input(
        "Type name",
        placeholder="PTO, Sick, Well-being, Personal...",
        key=PTO_FORM_FIELDS["name"],
    )
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
        elif st.session_state.editing_pto_name is None:
            st.session_state.pto_types.append({
                "name": clean_name,
                "current_balance": float(current_balance),
                "balance_unit": balance_unit,
                "accrual_amount": float(accrual_amount),
                "accrual_unit": accrual_unit,
                "accrual_frequency": accrual_frequency,
            })
            st.session_state.editing_pto_name = clean_name
            st.success(f"Added PTO type: {clean_name}")
            st.rerun()
        else:
            original_name = st.session_state.editing_pto_name
            for item in st.session_state.pto_types:
                if item["name"] == original_name:
                    item.update({
                        "name": clean_name,
                        "current_balance": float(current_balance),
                        "balance_unit": balance_unit,
                        "accrual_amount": float(accrual_amount),
                        "accrual_unit": accrual_unit,
                        "accrual_frequency": accrual_frequency,
                    })
                    break

            for entry in st.session_state.planned_time_off:
                if entry["pto_type"] == original_name:
                    entry["pto_type"] = clean_name

            st.session_state.editing_pto_name = clean_name
            st.success(f"Updated PTO type: {clean_name}")
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
    pto_df = pd.DataFrame(st.session_state.pto_types)
    st.dataframe(pto_df, use_container_width=True, hide_index=True)
else:
    st.info("Add at least one PTO type to start projecting balances.")

st.subheader("2) Add planned time off")
if st.session_state.pto_types:
    valid_pto_names = [item["name"] for item in st.session_state.pto_types]
    if st.session_state.get(TIME_OFF_FORM_FIELDS["pto_type"]) not in valid_pto_names:
        st.session_state[TIME_OFF_FORM_FIELDS["pto_type"]] = valid_pto_names[0]

    time_off_options = ["Add new planned time off"] + [
        f"{i}: {entry['date']} | {entry['pto_type']} | {entry['amount']} {entry['unit']}"
        + (f" | {entry.get('reason', '').strip()}" if entry.get("reason", "").strip() else "")
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
        None
        if selected_time_off_option == "Add new planned time off"
        else int(selected_time_off_option.split(":", 1)[0])
    )
    if st.session_state.editing_time_off_index != target_time_off_index:
        set_time_off_edit_selection(target_time_off_index, start_date)

    with st.form("time_off_form"):
        d1, d2, d3, d4 = st.columns([1.4, 1.1, 1.1, 1.2])
        time_off_date = d1.date_input("Date", key=TIME_OFF_FORM_FIELDS["date"])
        pto_type = d2.selectbox(
            "PTO type",
            [x["name"] for x in st.session_state.pto_types],
            key=TIME_OFF_FORM_FIELDS["pto_type"],
        )
        amount_value = d3.number_input(
            "Amount",
            min_value=0.0,
            step=0.5,
            key=TIME_OFF_FORM_FIELDS["amount"],
        )
        amount_unit = d4.selectbox("Unit", ["days", "hours"], key=TIME_OFF_FORM_FIELDS["unit"])
        reason = st.text_input(
            "Reason (optional)",
            placeholder="Vacation, doctor's appointment, holiday travel...",
            key=TIME_OFF_FORM_FIELDS["reason"],
        )
        time_off_action = (
            "Add planned time off" if st.session_state.editing_time_off_index is None else "Save time off changes"
        )
        time_off_submitted = st.form_submit_button(time_off_action)

        if time_off_submitted:
            entry_data = {
                "date": time_off_date,
                "pto_type": pto_type,
                "amount": float(amount_value),
                "unit": amount_unit,
                "reason": reason.strip(),
            }
            if st.session_state.editing_time_off_index is None:
                st.session_state.planned_time_off.append(entry_data)
                st.success("Planned time off added.")
            else:
                st.session_state.planned_time_off[st.session_state.editing_time_off_index] = entry_data
                st.success("Planned time off updated.")
            st.session_state.editing_time_off_index = None
            st.session_state.confirm_delete_time_off_index = None
            st.rerun()

    if st.session_state.editing_time_off_index is not None and st.button("Delete selected planned time off"):
        st.session_state.planned_time_off.pop(st.session_state.editing_time_off_index)
        st.session_state.editing_time_off_index = None
        st.session_state.confirm_delete_time_off_index = None
        st.rerun()

    if st.session_state.confirm_delete_time_off_index is not None:
        if st.button("Reset pending delete", key="reset_pending_delete"):
            st.session_state.confirm_delete_time_off_index = None
            st.rerun()

        components.html(
            """
            <script>
            const parentDoc = window.parent.document;
            const activeConfirmButton = Array.from(parentDoc.querySelectorAll("button"))
              .find((button) => button.innerText.trim() === "Confirm");
            const resetButton = Array.from(parentDoc.querySelectorAll("button"))
              .find((button) => button.innerText.trim() === "Reset pending delete");

            if (resetButton) {
              resetButton.style.display = "none";
            }

            if (activeConfirmButton && resetButton && !parentDoc.__ptoConfirmResetListenerAttached) {
              parentDoc.__ptoConfirmResetListenerAttached = true;
              parentDoc.addEventListener(
                "click",
                (event) => {
                  const currentConfirmButton = Array.from(parentDoc.querySelectorAll("button"))
                    .find((button) => button.innerText.trim() === "Confirm");
                  const currentResetButton = Array.from(parentDoc.querySelectorAll("button"))
                    .find((button) => button.innerText.trim() === "Reset pending delete");

                  if (!currentConfirmButton || !currentResetButton) {
                    parentDoc.__ptoConfirmResetListenerAttached = false;
                    return;
                  }

                  if (!currentConfirmButton.contains(event.target)) {
                    currentResetButton.click();
                  }
                },
                true
              );
            }
            </script>
            """,
            height=0,
        )

    if st.session_state.planned_time_off:
        st.markdown("### Planned time off entries")
        header_cols = st.columns([1.2, 1.2, 0.9, 2.4, 0.6])
        header_cols[0].markdown("**Date**")
        header_cols[1].markdown("**PTO Type**")
        header_cols[2].markdown("**Amount**")
        header_cols[3].markdown("**Reason**")
        header_cols[4].markdown("**Delete**")

        sorted_entries = sorted(
            enumerate(st.session_state.planned_time_off),
            key=lambda item: item[1]["date"],
        )
        for idx, entry in sorted_entries:
            row_cols = st.columns([1.2, 1.2, 0.9, 2.4, 0.6])
            row_cols[0].write(str(entry["date"]))
            row_cols[1].write(entry["pto_type"])
            row_cols[2].write(f"{entry['amount']} {entry['unit']}")
            row_cols[3].write(entry.get("reason", "").strip() or "-")

            delete_label = "Confirm" if st.session_state.confirm_delete_time_off_index == idx else "🗑"
            if row_cols[4].button(delete_label, key=f"delete_time_off_{idx}", type="primary"):
                if st.session_state.confirm_delete_time_off_index == idx:
                    st.session_state.planned_time_off.pop(idx)
                    st.session_state.confirm_delete_time_off_index = None
                    if st.session_state.editing_time_off_index == idx:
                        st.session_state.editing_time_off_index = None
                    elif (
                        st.session_state.editing_time_off_index is not None
                        and st.session_state.editing_time_off_index > idx
                    ):
                        st.session_state.editing_time_off_index -= 1
                    st.rerun()
                else:
                    st.session_state.confirm_delete_time_off_index = idx
                    st.rerun()
st.subheader("3) Weekly balance projection")

if st.session_state.pto_types:
    pto_types = st.session_state.pto_types
    time_off_entries = st.session_state.planned_time_off

    balances = {
        item["name"]: float(item["current_balance"]) * UNIT_TO_HOURS[item["balance_unit"]]
        for item in pto_types
    }

    time_off_by_week = {}
    for entry in time_off_entries:
        week_start = entry["date"] - timedelta(days=entry["date"].weekday())
        amount_hours = entry["amount"] * UNIT_TO_HOURS[entry["unit"]]
        key = (week_start, entry["pto_type"])
        time_off_by_week[key] = time_off_by_week.get(key, 0.0) + amount_hours

    rows = []
    projection_start = start_date - timedelta(days=start_date.weekday())

    per_week_accrual = {
        item["name"]: accrual_hours_per_week(item["accrual_amount"], item["accrual_unit"], item["accrual_frequency"])
        for item in pto_types
    }

    for week_num in range(weeks_to_project):
        week_start = projection_start + timedelta(weeks=week_num)
        week_end = week_start + timedelta(days=6)

        row = {
            "Week #": week_num + 1,
            "Week Start": week_start,
            "Week End": week_end,
        }

        for item in pto_types:
            name = item["name"]
            accrued = per_week_accrual[name]
            used = time_off_by_week.get((week_start, name), 0.0)
            balances[name] += accrued
            balances[name] -= used

            row[f"{name} Accrued (hrs)"] = round(accrued, 2)
            row[f"{name} Used (hrs)"] = round(used, 2)
            row[f"{name} Balance (hrs)"] = round(balances[name], 2)
            row[f"{name} Balance (days)"] = round(balances[name] / hours_per_day, 2)

        rows.append(row)

    projection_df = pd.DataFrame(rows)

    total_negative = False
    for item in pto_types:
        if (projection_df[f"{item['name']} Balance (hrs)"] < 0).any():
            total_negative = True
            break

    metric_cols = st.columns(len(pto_types))
    for col, item in zip(metric_cols, pto_types):
        final_hrs = float(projection_df.iloc[-1][f"{item['name']} Balance (hrs)"])
        final_days = float(projection_df.iloc[-1][f"{item['name']} Balance (days)"])
        col.metric(item["name"], f"{final_hrs:.2f} hrs", f"{final_days:.2f} days")

    if total_negative:
        st.warning("One or more PTO types go negative during the projection.")

    st.dataframe(projection_df, use_container_width=True, hide_index=True)

    st.line_chart(
        projection_df.set_index("Week Start")[[f"{item['name']} Balance (hrs)" for item in pto_types]],
        use_container_width=True,
    )

    csv = projection_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download projection as CSV", data=csv, file_name="pto_projection.csv", mime="text/csv")

    st.markdown("### Notes")
    st.markdown(
        "- Current balances can be entered in **hours** or **days**.\n"
        "- Planned time off can be entered in hours or days.\n"
        "- Accrual is spread evenly across each week for weekly projections."
    )
else:
    st.info("Once you add PTO types, your weekly projection will appear here.")
