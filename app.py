import streamlit as st
import fitz  # PyMuPDF
import json
import os
from google import genai
from google.genai import types
from jinja2 import Template
from weasyprint import HTML

# HTML/CSS Template for the output PDF
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <style>
    @page { size: A4; margin: 20mm; }
    body { font-family: Arial, sans-serif; color: #2d3748; line-height: 1.5; }
    h1 { color: #1a365d; border-bottom: 3px solid #3182ce; padding-bottom: 8px; font-size: 24px; }
    h2 { color: #2c5282; margin-top: 24px; font-size: 18px; border-bottom: 1px solid #e2e8f0; }
    .card { background: #f7fafc; border-left: 4px solid #3182ce; padding: 10px 14px; margin: 10px 0; border-radius: 2px; }
    .term { font-weight: bold; color: #2b6cb0; }
    ul { padding-left: 20px; }
    li { margin-bottom: 6px; }
  </style>
</head>
<body>
  <h1>{{ data.title }}</h1>

  <h2>Key Definitions</h2>
  {% for item in data.key_terms %}
    <p><span class="term">{{ item.term }}:</span> {{ item.definition }}</p>
  {% endfor %}

  <h2>Core Concepts</h2>
  <ul>
    {% for point in data.core_points %}
      <li>{{ point }}</li>
    {% endfor %}
  </ul>

  <h2>Self-Quiz</h2>
  {% for q in data.quiz %}
    <div class="card">
      <p><strong>Q: {{ q.question }}</strong></p>
      <p><em>A: {{ q.answer }}</em></p>
    </div>
  {% endfor %}
</body>
</html>
"""

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract raw text from uploaded PDF bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join([page.get_text() for page in doc])

def generate_study_data(text: str) -> dict:
    """Send text to Gemini API and receive structured JSON."""
    
    # Get API key explicitly from environment or Streamlit secrets
    api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Please set it in environment or secrets.toml.")

    # Pass the api_key directly to the Client
    client = genai.Client(api_key=api_key)
    
    prompt = f"Analyze these lecture notes and generate a structured study guide:\n\n{text[:10000]}"

    response = client.models.generate_content(
        model='gemini-2.5-flash',
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
                                "definition": {"type": "STRING"}
                            }
                        }
                    },
                    "core_points": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "quiz": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "question": {"type": "STRING"},
                                "answer": {"type": "STRING"}
                            }
                        }
                    }
                },
                "required": ["title", "key_terms", "core_points", "quiz"]
            }
        )
    )
    return json.loads(response.text)


def render_pdf(data: dict) -> bytes:
    """Render structured JSON data to PDF bytes via WeasyPrint."""
    template = Template(HTML_TEMPLATE)
    html_out = template.render(data=data)
    return HTML(string=html_out).write_pdf()

# Streamlit UI
st.set_page_config(page_title="PDF Study Guide Generator", layout="centered")

st.title("📚 PDF-to-PDF Study Assistant")
st.write("Upload your lecture notes, slides, or syllabus to get a structured study guide PDF.")

uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

if uploaded_file is not None:
    if st.button("Generate Study Guide", type="primary"):
        with st.spinner("Extracting text and generating structured guide..."):
            try:
                # 1. Read input PDF
                pdf_bytes = uploaded_file.read()
                raw_text = extract_text_from_pdf(pdf_bytes)

                # 2. Extract structured content via LLM
                study_data = generate_study_data(raw_text)

                # 3. Render HTML to PDF
                output_pdf_bytes = render_pdf(study_data)

                st.success("Study guide generated successfully!")

                # 4. Download button
                st.download_button(
                    label="📥 Download Study Guide PDF",
                    data=output_pdf_bytes,
                    file_name=f"Study_Guide_{uploaded_file.name}",
                    mime="application/pdf"
                )

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
