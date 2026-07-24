import io
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

st.set_page_config(page_title="Suprime Guest Quotation Calculator", page_icon="🏨", layout="wide")

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "saved_quotations.csv"
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "suprime_logo.png"

COMPANY_DETAILS = {
    "business_name": "Suprime Hotels and Conference",
    "registration_number": "Registration number: [To be added]",
    "vat_number": "VAT number: [To be added]",
    "physical_address": "Physical address: [To be added]",
    "email_address": "Email: [To be added]",
    "telephone_number": "Telephone: [To be added]",
    "banking_details": "Banking details: [To be added]",
    "quotation_validity_period": "30 days",
    "terms_and_conditions": [
        "Rates are subject to availability at the time of confirmation.",
        "A 50% deposit is required to secure the booking.",
        "Final confirmation is subject to written acceptance by the client.",
    ],
}

REGISTER_COLUMNS = [
    "quotation_number",
    "date",
    "client",
    "arrival_date",
    "departure_date",
    "total",
    "status",
    "date_created",
]


def format_currency(amount: float) -> str:
    return f"R{amount:,.2f}"


def sanitize_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", " ", value).strip()
    return value or "quotation"


def ensure_register_file() -> None:
    if not DATA_FILE.exists():
        pd.DataFrame(columns=REGISTER_COLUMNS).to_csv(DATA_FILE, index=False)
        return

    try:
        existing_df = pd.read_csv(DATA_FILE)
    except pd.errors.EmptyDataError:
        pd.DataFrame(columns=REGISTER_COLUMNS).to_csv(DATA_FILE, index=False)
        return

    if set(REGISTER_COLUMNS).issubset(existing_df.columns):
        return

    if "quotation_number" in existing_df.columns and "client_name" in existing_df.columns:
        migrated_rows = []
        for _, row in existing_df.iterrows():
            migrated_rows.append(
                {
                    "quotation_number": row.get("quotation_number", ""),
                    "date": row.get("quotation_date", date.today().isoformat()),
                    "client": row.get("client_name", row.get("guest_name", "")),
                    "arrival_date": row.get("arrival_date", ""),
                    "departure_date": row.get("departure_date", ""),
                    "total": row.get("final_quotation_amount", 0),
                    "status": "Saved",
                    "date_created": date.today().isoformat(),
                }
            )
        migrated_df = pd.DataFrame(migrated_rows, columns=REGISTER_COLUMNS)
        migrated_df.to_csv(DATA_FILE, index=False)
    else:
        pd.DataFrame(columns=REGISTER_COLUMNS).to_csv(DATA_FILE, index=False)


def init_session_state() -> None:
    defaults = {
        "quotation_number": "Q0001",
        "quotation_date": date.today(),
        "client_name": "Sunset Lodge",
        "contact_person": "Aisha Ndlovu",
        "email_address": "aisha@sunsetlodge.co.za",
        "telephone_number": "011 555 1234",
        "guest_name": "Nomsa Khumalo",
        "arrival_date": date.today(),
        "departure_date": date.today() + timedelta(days=2),
        "number_of_guests": 2,
        "number_of_rooms": 1,
        "rate_per_room_per_night": 1200.0,
        "breakfast_cost": 150.0,
        "dinner_cost": 240.0,
        "transport_cost": 300.0,
        "conference_cost": 0.0,
        "laundry_cost": 0.0,
        "other_charges": 100.0,
        "other_charges_description": "Late checkout requested.",
        "discount_percentage": 10.0,
        "vat_applicable": True,
        "client_notes": "Please confirm the room allocation before final payment.",
        "terms_and_conditions": "Prices are valid for 30 days from the quotation date.",
        "calculated_totals": None,
        "validation_errors": [],
        "preview_ready": False,
        "saved_success": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def calculate_totals(
    arrival_date: date,
    departure_date: date,
    number_of_guests: int,
    number_of_rooms: int,
    rate_per_room_per_night: float,
    breakfast_cost: float,
    dinner_cost: float,
    transport_cost: float,
    conference_cost: float,
    laundry_cost: float,
    other_charges: float,
    discount_percentage: float,
    vat_applicable: bool,
) -> dict:
    number_of_nights = max((departure_date - arrival_date).days, 0)
    accommodation_total = round(rate_per_room_per_night * number_of_rooms * number_of_nights, 2)
    breakfast_total = round(float(breakfast_cost), 2)
    dinner_total = round(float(dinner_cost), 2)
    transport_total = round(float(transport_cost), 2)
    conference_total = round(float(conference_cost), 2)
    laundry_total = round(float(laundry_cost), 2)
    other_total = round(float(other_charges), 2)

    subtotal = round(
        accommodation_total + breakfast_total + dinner_total + transport_total + conference_total + laundry_total + other_total,
        2,
    )
    discount_amount = round(subtotal * (discount_percentage / 100), 2)
    discounted_subtotal = round(subtotal - discount_amount, 2)
    vat_amount = round(discounted_subtotal * 0.15, 2) if vat_applicable else 0.0
    final_total = round(discounted_subtotal + vat_amount, 2)

    return {
        "number_of_nights": number_of_nights,
        "accommodation_total": accommodation_total,
        "breakfast_total": breakfast_total,
        "dinner_total": dinner_total,
        "transport_total": transport_total,
        "conference_total": conference_total,
        "laundry_total": laundry_total,
        "other_total": other_total,
        "subtotal": subtotal,
        "discount_percentage": float(discount_percentage),
        "discount_amount": discount_amount,
        "vat_applicable": vat_applicable,
        "vat_amount": vat_amount,
        "final_total": final_total,
    }


def validate_form_data() -> list[str]:
    errors: list[str] = []
    if not st.session_state.get("quotation_number", "").strip():
        errors.append("Quotation number is required.")
    if not st.session_state.get("client_name", "").strip():
        errors.append("Client or company name is required.")
    if not st.session_state.get("contact_person", "").strip():
        errors.append("Contact person is required.")
    if not st.session_state.get("email_address", "").strip():
        errors.append("Email address is required.")
    if not st.session_state.get("telephone_number", "").strip():
        errors.append("Telephone number is required.")
    if not st.session_state.get("guest_name", "").strip():
        errors.append("Guest name or group name is required.")
    if st.session_state.get("departure_date", date.today()) < st.session_state.get("arrival_date", date.today()):
        errors.append("Departure date cannot be before arrival date.")
    if st.session_state.get("number_of_guests", 0) < 0:
        errors.append("Number of guests cannot be negative.")
    if st.session_state.get("number_of_rooms", 0) < 0:
        errors.append("Number of rooms cannot be negative.")
    if st.session_state.get("rate_per_room_per_night", 0) < 0:
        errors.append("Rate per room per night cannot be negative.")
    for field_name in ["breakfast_cost", "dinner_cost", "transport_cost", "conference_cost", "laundry_cost", "other_charges"]:
        if st.session_state.get(field_name, 0) < 0:
            errors.append(f"{field_name.replace('_', ' ').title()} cannot be negative.")
    if st.session_state.get("discount_percentage", 0) < 0 or st.session_state.get("discount_percentage", 0) > 100:
        errors.append("Discount percentage must be between 0 and 100.")
    return errors


def get_current_quote_data() -> dict:
    totals = calculate_totals(
        st.session_state.get("arrival_date", date.today()),
        st.session_state.get("departure_date", date.today()),
        int(st.session_state.get("number_of_guests", 0)),
        int(st.session_state.get("number_of_rooms", 0)),
        float(st.session_state.get("rate_per_room_per_night", 0.0)),
        float(st.session_state.get("breakfast_cost", 0.0)),
        float(st.session_state.get("dinner_cost", 0.0)),
        float(st.session_state.get("transport_cost", 0.0)),
        float(st.session_state.get("conference_cost", 0.0)),
        float(st.session_state.get("laundry_cost", 0.0)),
        float(st.session_state.get("other_charges", 0.0)),
        float(st.session_state.get("discount_percentage", 0.0)),
        bool(st.session_state.get("vat_applicable", True)),
    )
    return {
        "quotation_number": st.session_state.get("quotation_number", ""),
        "quotation_date": st.session_state.get("quotation_date", date.today()).strftime("%Y-%m-%d"),
        "client_name": st.session_state.get("client_name", ""),
        "contact_person": st.session_state.get("contact_person", ""),
        "email_address": st.session_state.get("email_address", ""),
        "telephone_number": st.session_state.get("telephone_number", ""),
        "guest_name": st.session_state.get("guest_name", ""),
        "arrival_date": st.session_state.get("arrival_date", date.today()).strftime("%Y-%m-%d"),
        "departure_date": st.session_state.get("departure_date", date.today()).strftime("%Y-%m-%d"),
        "number_of_nights": totals["number_of_nights"],
        "number_of_guests": int(st.session_state.get("number_of_guests", 0)),
        "number_of_rooms": int(st.session_state.get("number_of_rooms", 0)),
        "rate_per_room_per_night": float(st.session_state.get("rate_per_room_per_night", 0.0)),
        "breakfast_cost": float(st.session_state.get("breakfast_cost", 0.0)),
        "dinner_cost": float(st.session_state.get("dinner_cost", 0.0)),
        "transport_cost": float(st.session_state.get("transport_cost", 0.0)),
        "conference_cost": float(st.session_state.get("conference_cost", 0.0)),
        "laundry_cost": float(st.session_state.get("laundry_cost", 0.0)),
        "other_charges": float(st.session_state.get("other_charges", 0.0)),
        "other_charges_description": st.session_state.get("other_charges_description", ""),
        "discount_percentage": float(st.session_state.get("discount_percentage", 0.0)),
        "vat_applicable": bool(st.session_state.get("vat_applicable", True)),
        "client_notes": st.session_state.get("client_notes", ""),
        "terms_and_conditions": st.session_state.get("terms_and_conditions", ""),
        "totals": totals,
    }


def build_preview_markdown(quote_data: dict) -> str:
    totals = quote_data["totals"]
    line_items = [
        ("Accommodation", quote_data["number_of_rooms"], quote_data["number_of_nights"], quote_data["rate_per_room_per_night"], totals["accommodation_total"]),
        ("Breakfast", quote_data["number_of_guests"], "-", 1.0, totals["breakfast_total"]),
        ("Dinner", quote_data["number_of_guests"], "-", 1.0, totals["dinner_total"]),
        ("Transport", 1, "-", 1.0, totals["transport_total"]),
        ("Conference / Venue", 1, "-", 1.0, totals["conference_total"]),
        ("Laundry", 1, "-", 1.0, totals["laundry_total"]),
        ("Other Charges", 1, "-", 1.0, totals["other_total"]),
    ]

    table_rows = [
        "| Item | Qty | Nights | Unit Price | Line Total |",
        "|---|---:|---:|---:|---:|",
    ]
    for description, quantity, nights, unit_price, line_total in line_items:
        table_rows.append(
            f"| {description} | {quantity} | {nights} | {format_currency(unit_price)} | {format_currency(line_total)} |"
        )

    summary_lines = [
        "## Quotation Preview",
        "",
        f"**{COMPANY_DETAILS['business_name']}**",
        f"{COMPANY_DETAILS['physical_address']}",
        f"{COMPANY_DETAILS['email_address']} | {COMPANY_DETAILS['telephone_number']}",
        "",
        f"Quotation Number: **{quote_data['quotation_number']}**",
        f"Quotation Date: **{quote_data['quotation_date']}**",
        f"Client: **{quote_data['client_name']}**",
        f"Contact Person: **{quote_data['contact_person']}**",
        f"Email: **{quote_data['email_address']}**",
        f"Telephone: **{quote_data['telephone_number']}**",
        f"Guest / Group: **{quote_data['guest_name']}**",
        f"Arrival Date: **{quote_data['arrival_date']}**",
        f"Departure Date: **{quote_data['departure_date']}**",
        f"Number of Nights: **{quote_data['number_of_nights']}**",
        "",
        "### Itemised Quotation",
        "",
        "\n".join(table_rows),
        "",
        f"**Subtotal:** {format_currency(totals['subtotal'])}",
        f"**Discount:** {format_currency(totals['discount_amount'])}",
        f"**VAT:** {format_currency(totals['vat_amount']) if totals['vat_applicable'] else 'Not applicable'}",
        f"**Final Total:** {format_currency(totals['final_total'])}",
        "",
        f"**Notes:** {quote_data['client_notes'] or 'No notes provided.'}",
        f"**Terms and Conditions:** {quote_data['terms_and_conditions'] or COMPANY_DETAILS['terms_and_conditions'][0]}",
        f"**Validity:** {COMPANY_DETAILS['quotation_validity_period']}",
        "",
        "**Authorised by:** __________________________",
    ]
    return "\n".join(summary_lines)


def build_pdf_bytes(quote_data: dict) -> bytes:
    totals = quote_data["totals"]
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    heading_style = ParagraphStyle("Heading", parent=styles["Heading1"], fontSize=16, leading=20, spaceAfter=8)
    body_style = styles["BodyText"]
    small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=8, leading=10, textColor=colors.grey)

    story = []
    if LOGO_PATH.exists():
        try:
            from reportlab.lib.utils import ImageReader

            story.append(Paragraph(f"<img src='{LOGO_PATH}' width='120' height='60'/>", styles["BodyText"]))
        except Exception:
            story.append(Paragraph(COMPANY_DETAILS["business_name"], heading_style))
    else:
        story.append(Paragraph(COMPANY_DETAILS["business_name"], heading_style))

    story.append(Paragraph(COMPANY_DETAILS["physical_address"], body_style))
    story.append(Paragraph(f"{COMPANY_DETAILS['email_address']} | {COMPANY_DETAILS['telephone_number']}", body_style))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Quotation", heading_style))
    story.append(Paragraph(f"Quotation Number: {quote_data['quotation_number']}", body_style))
    story.append(Paragraph(f"Date: {quote_data['quotation_date']}", body_style))
    story.append(Paragraph(f"Client: {quote_data['client_name']}", body_style))
    story.append(Paragraph(f"Contact Person: {quote_data['contact_person']}", body_style))
    story.append(Paragraph(f"Email: {quote_data['email_address']}", body_style))
    story.append(Paragraph(f"Telephone: {quote_data['telephone_number']}", body_style))
    story.append(Paragraph(f"Guest / Group: {quote_data['guest_name']}", body_style))
    story.append(Paragraph(f"Arrival: {quote_data['arrival_date']} | Departure: {quote_data['departure_date']}", body_style))
    story.append(Spacer(1, 4 * mm))

    table_data = [
        ["Item", "Qty", "Nights", "Unit Price", "Line Total"],
        ["Accommodation", str(quote_data["number_of_rooms"]), str(quote_data["number_of_nights"]), format_currency(quote_data["rate_per_room_per_night"]), format_currency(totals["accommodation_total"])],
        ["Breakfast", str(quote_data["number_of_guests"]), "-", format_currency(1.0), format_currency(totals["breakfast_total"])],
        ["Dinner", str(quote_data["number_of_guests"]), "-", format_currency(1.0), format_currency(totals["dinner_total"])],
        ["Transport", "1", "-", format_currency(1.0), format_currency(totals["transport_total"])],
        ["Conference / Venue", "1", "-", format_currency(1.0), format_currency(totals["conference_total"])],
        ["Laundry", "1", "-", format_currency(1.0), format_currency(totals["laundry_total"])],
        ["Other Charges", "1", "-", format_currency(1.0), format_currency(totals["other_total"])],
    ]
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Subtotal: {format_currency(totals['subtotal'])}", body_style))
    story.append(Paragraph(f"Discount: {format_currency(totals['discount_amount'])}", body_style))
    story.append(Paragraph(f"VAT: {format_currency(totals['vat_amount']) if totals['vat_applicable'] else 'Not applicable'}", body_style))
    story.append(Paragraph(f"Final Total: {format_currency(totals['final_total'])}", body_style))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Notes: {quote_data['client_notes'] or 'No notes provided.'}", body_style))
    story.append(Paragraph(f"Terms and Conditions: {quote_data['terms_and_conditions'] or COMPANY_DETAILS['terms_and_conditions'][0]}", body_style))
    story.append(Paragraph(f"Validity: {COMPANY_DETAILS['quotation_validity_period']}", body_style))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Authorised by: __________________________", body_style))
    story.append(Paragraph("Registration number: [To be added]", small_style))
    story.append(Paragraph("VAT number: [To be added]", small_style))
    document.build(story)
    return buffer.getvalue()


def save_quote_to_register(quote_data: dict) -> None:
    register_df = pd.read_csv(DATA_FILE)
    new_row = {
        "quotation_number": quote_data["quotation_number"],
        "date": quote_data["quotation_date"],
        "client": quote_data["client_name"],
        "arrival_date": quote_data["arrival_date"],
        "departure_date": quote_data["departure_date"],
        "total": round(quote_data["totals"]["final_total"], 2),
        "status": "Saved",
        "date_created": date.today().isoformat(),
    }
    updated_df = pd.concat([register_df, pd.DataFrame([new_row])], ignore_index=True)
    updated_df.to_csv(DATA_FILE, index=False)


def reset_form() -> None:
    for key in [
        "quotation_number",
        "quotation_date",
        "client_name",
        "contact_person",
        "email_address",
        "telephone_number",
        "guest_name",
        "arrival_date",
        "departure_date",
        "number_of_guests",
        "number_of_rooms",
        "rate_per_room_per_night",
        "breakfast_cost",
        "dinner_cost",
        "transport_cost",
        "conference_cost",
        "laundry_cost",
        "other_charges",
        "other_charges_description",
        "discount_percentage",
        "vat_applicable",
        "client_notes",
        "terms_and_conditions",
        "calculated_totals",
        "validation_errors",
        "preview_ready",
        "saved_success",
    ]:
        if key in st.session_state:
            del st.session_state[key]
    init_session_state()


def render_company_header() -> None:
    st.title("🏨 Suprime Guest Quotation Calculator")
    st.caption("Professional quotation builder with preview, local savings, and PDF export.")
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=220)
    else:
        st.info("Logo file not found. Save your image as assets/suprime_logo.png to display it in the quotation preview and PDF.")


ensure_register_file()
init_session_state()

render_company_header()

with st.sidebar:
    st.header("Workflow")
    st.write("Use the buttons below to calculate, preview, save, export, or clear the quotation.")
    if st.button("Calculate", use_container_width=True):
        errors = validate_form_data()
        st.session_state["validation_errors"] = errors
        st.session_state["preview_ready"] = False
        if not errors:
            st.session_state["calculated_totals"] = calculate_totals(
                st.session_state.get("arrival_date", date.today()),
                st.session_state.get("departure_date", date.today()),
                int(st.session_state.get("number_of_guests", 0)),
                int(st.session_state.get("number_of_rooms", 0)),
                float(st.session_state.get("rate_per_room_per_night", 0.0)),
                float(st.session_state.get("breakfast_cost", 0.0)),
                float(st.session_state.get("dinner_cost", 0.0)),
                float(st.session_state.get("transport_cost", 0.0)),
                float(st.session_state.get("conference_cost", 0.0)),
                float(st.session_state.get("laundry_cost", 0.0)),
                float(st.session_state.get("other_charges", 0.0)),
                float(st.session_state.get("discount_percentage", 0.0)),
                bool(st.session_state.get("vat_applicable", True)),
            )
            st.session_state["saved_success"] = False

    if st.button("Generate Quotation", use_container_width=True):
        errors = validate_form_data()
        st.session_state["validation_errors"] = errors
        if not errors:
            st.session_state["calculated_totals"] = calculate_totals(
                st.session_state.get("arrival_date", date.today()),
                st.session_state.get("departure_date", date.today()),
                int(st.session_state.get("number_of_guests", 0)),
                int(st.session_state.get("number_of_rooms", 0)),
                float(st.session_state.get("rate_per_room_per_night", 0.0)),
                float(st.session_state.get("breakfast_cost", 0.0)),
                float(st.session_state.get("dinner_cost", 0.0)),
                float(st.session_state.get("transport_cost", 0.0)),
                float(st.session_state.get("conference_cost", 0.0)),
                float(st.session_state.get("laundry_cost", 0.0)),
                float(st.session_state.get("other_charges", 0.0)),
                float(st.session_state.get("discount_percentage", 0.0)),
                bool(st.session_state.get("vat_applicable", True)),
            )
            st.session_state["preview_ready"] = True
            st.session_state["saved_success"] = False

    if st.button("Save Quotation", use_container_width=True):
        errors = validate_form_data()
        st.session_state["validation_errors"] = errors
        if not errors:
            quote_data = get_current_quote_data()
            save_quote_to_register(quote_data)
            st.session_state["preview_ready"] = True
            st.session_state["saved_success"] = True
            st.session_state["calculated_totals"] = quote_data["totals"]

    if st.button("Clear Form", use_container_width=True):
        reset_form()

    st.markdown("---")
    st.subheader("Company details")
    st.write(COMPANY_DETAILS["business_name"])
    st.write(COMPANY_DETAILS["registration_number"])
    st.write(COMPANY_DETAILS["vat_number"])
    st.write(COMPANY_DETAILS["physical_address"])
    st.write(COMPANY_DETAILS["email_address"])
    st.write(COMPANY_DETAILS["telephone_number"])
    st.write(COMPANY_DETAILS["banking_details"])

builder_tab, saved_tab = st.tabs(["Quotation Builder", "Saved Quotations"])

with builder_tab:
    st.subheader("Client Details")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Quotation number", key="quotation_number")
        st.date_input("Quotation date", key="quotation_date")
        st.text_input("Client or company name", key="client_name")
        st.text_input("Contact person", key="contact_person")
        st.text_input("Email address", key="email_address")
        st.text_input("Telephone number", key="telephone_number")
        st.text_input("Guest name or group name", key="guest_name")
    with col2:
        st.date_input("Arrival date", key="arrival_date")
        st.date_input("Departure date", key="departure_date")
        st.number_input("Number of guests", min_value=0, step=1, key="number_of_guests")
        st.number_input("Number of rooms", min_value=0, step=1, key="number_of_rooms")
        st.number_input("Rate per room per night (R)", min_value=0.0, step=50.0, key="rate_per_room_per_night")

    st.markdown("---")
    st.subheader("Accommodation Details")
    col3, col4 = st.columns(2)
    with col3:
        st.caption("Calculated automatically")
        if st.session_state.get("calculated_totals"):
            st.metric("Number of nights", st.session_state["calculated_totals"]["number_of_nights"])
            st.metric("Accommodation total", format_currency(st.session_state["calculated_totals"]["accommodation_total"]))
    with col4:
        st.caption("Service charges")
        st.number_input("Breakfast (R)", min_value=0.0, step=10.0, key="breakfast_cost")
        st.number_input("Dinner (R)", min_value=0.0, step=10.0, key="dinner_cost")
        st.number_input("Transport (R)", min_value=0.0, step=10.0, key="transport_cost")
        st.number_input("Conference / venue (R)", min_value=0.0, step=10.0, key="conference_cost")
        st.number_input("Laundry (R)", min_value=0.0, step=10.0, key="laundry_cost")
        st.number_input("Other charges (R)", min_value=0.0, step=10.0, key="other_charges")
        st.text_input("Description of other charges", key="other_charges_description")

    st.markdown("---")
    st.subheader("Discounts and Notes")
    col5, col6 = st.columns(2)
    with col5:
        st.number_input("Discount percentage (%)", min_value=0.0, max_value=100.0, step=1.0, key="discount_percentage")
        st.checkbox("VAT applies (15%)", key="vat_applicable")
    with col6:
        st.text_area("Client notes", key="client_notes")
        st.text_area("Quotation terms and conditions", key="terms_and_conditions")

    st.markdown("---")
    if st.session_state.get("validation_errors"):
        st.error("Please correct the following issues:")
        for issue in st.session_state["validation_errors"]:
            st.write(f"- {issue}")

    if st.session_state.get("saved_success"):
        st.success("Quotation saved successfully.")

    if st.session_state.get("calculated_totals"):
        totals = st.session_state["calculated_totals"]
        st.subheader("Quotation Summary")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Accommodation", format_currency(totals["accommodation_total"]))
        c2.metric("Breakfast", format_currency(totals["breakfast_total"]))
        c3.metric("Dinner", format_currency(totals["dinner_total"]))
        c4.metric("Discount", format_currency(totals["discount_amount"]))
        c5.metric("Final total", format_currency(totals["final_total"]))

    if st.session_state.get("preview_ready"):
        quote_data = get_current_quote_data()
        st.markdown("---")
        st.subheader("Client Quotation Preview")
        st.markdown(build_preview_markdown(quote_data))

        pdf_bytes = build_pdf_bytes(quote_data)
        st.download_button(
            label="Download Quotation as PDF",
            data=pdf_bytes,
            file_name=f"Suprime Quotation {sanitize_filename(quote_data['quotation_number'])} {sanitize_filename(quote_data['client_name'])}.pdf",
            mime="application/pdf",
        )

with saved_tab:
    st.subheader("Saved Quotations Register")
    if DATA_FILE.exists():
        register_df = pd.read_csv(DATA_FILE)
        if not register_df.empty:
            display_df = register_df[["quotation_number", "date", "client", "arrival_date", "departure_date", "total", "status", "date_created"]]
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No quotations have been saved yet.")
    else:
        st.info("No quotations have been saved yet.")
