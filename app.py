import io
import json
import os

import fitz  # PyMuPDF
import streamlit as st
from google import genai
from google.genai import types
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract raw text from uploaded PDF bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc if page.get_text().strip())


def _get_api_key() -> str:
    """Get the Gemini API key from environment variables or Streamlit secrets."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            api_key = None

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Add it to Streamlit Cloud Secrets or your local environment."
        )
    return api_key


def generate_study_data(text: str) -> dict:
    """Send text to Gemini API and receive structured JSON."""
    client = genai.Client(api_key=_get_api_key())

    prompt = f"Analyze these lecture notes and generate a structured study guide:\n\n{text[:12000]}"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "key_terms": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "term": {"type": "STRING"},
                                "definition": {"type": "STRING"},
                            },
                        },
                    },
                    "core_points": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "quiz": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "question": {"type": "STRING"},
                                "answer": {"type": "STRING"},
                            },
                        },
                    },
                },
                "required": ["title", "key_terms", "core_points", "quiz"],
            },
        ),
    )
    return json.loads(response.text)


def render_pdf(data: dict) -> bytes:
    """Render structured JSON data to PDF bytes using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(data.get("title", "Study Guide"), styles["Title"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Key Definitions", styles["Heading2"]))

    for item in data.get("key_terms", []):
        term = item.get("term", "")
        definition = item.get("definition", "")
        story.append(Paragraph(f"<b>{term}</b>: {definition}", styles["BodyText"]))
        story.append(Spacer(1, 0.2 * cm))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Core Concepts", styles["Heading2"]))
    for point in data.get("core_points", []):
        story.append(Paragraph(f"• {point}", styles["BodyText"]))
        story.append(Spacer(1, 0.1 * cm))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Self-Quiz", styles["Heading2"]))
    for question in data.get("quiz", []):
        story.append(Paragraph(f"Q: {question.get('question', '')}", styles["BodyText"]))
        story.append(Paragraph(f"A: {question.get('answer', '')}", styles["BodyText"]))
        story.append(Spacer(1, 0.2 * cm))

    doc.build(story)
    return buffer.getvalue()


# Streamlit UI
st.set_page_config(page_title="PDF Study Guide Generator", layout="centered")

st.title("📚 PDF Study Guide Generator")
st.write("Upload a lecture PDF and create a structured study guide PDF.")
st.caption("For Streamlit Cloud, add your Gemini API key under Secrets as GEMINI_API_KEY.")

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file is not None:
    if st.button("Generate Study Guide", type="primary"):
        with st.spinner("Extracting text and generating the study guide..."):
            try:
                pdf_bytes = uploaded_file.read()
                raw_text = extract_text_from_pdf(pdf_bytes)
                study_data = generate_study_data(raw_text)
                output_pdf_bytes = render_pdf(study_data)

                st.success("Study guide generated successfully!")
                st.download_button(
                    label="📥 Download Study Guide PDF",
                    data=output_pdf_bytes,
                    file_name=f"Study_Guide_{uploaded_file.name}",
                    mime="application/pdf",
                )
            except Exception as exc:
                st.error(f"An error occurred: {exc}")
