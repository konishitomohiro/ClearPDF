import json
import os
import io
import base64

import fitz  # PyMuPDF
import streamlit as st
from google import genai
from google.genai import types
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# ---------------------------------------------------------
# 視覚・認知の最適化を施したHTML/CSSテンプレート
# ノイズ削減のため：色分け廃止、枠線廃止、カードデザイン廃止
# ---------------------------------------------------------
FONT_NAME = "HeiseiKakuGo-W5"
registerFont(UnicodeCIDFont(FONT_NAME))

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join([page.get_text() for page in doc])

def generate_study_data(text: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません。")

    client = genai.Client(api_key=api_key)
    prompt = (
        "以下の講義テキストを解析し、構造化された試験対策テキストを作成してください。"
        "出力はすべて日本語にしてください。\n\n"
        f"{text[:10000]}"
    )

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
    for style_name in ("Title", "Heading2", "BodyText"):
        styles[style_name].fontName = FONT_NAME

    story = []
    story.append(Paragraph(data.get("title", "学習ガイド"), styles["Title"]))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("1. 重要用語と解説", styles["Heading2"]))
    for item in data.get("key_terms", []):
        story.append(Paragraph(f"<b>{item.get('term', '')}</b>：{item.get('definition', '')}", styles["BodyText"]))
        story.append(Spacer(1, 0.2 * cm))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("2. 講義要点・概念", styles["Heading2"]))
    for point in data.get("core_points", []):
        story.append(Paragraph(f"・{point}", styles["BodyText"]))
        story.append(Spacer(1, 0.1 * cm))

    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("3. セルフチェック問題", styles["Heading2"]))
    for item in data.get("quiz", []):
        story.append(Paragraph(f"問：{item.get('question', '')}", styles["BodyText"]))
        story.append(Paragraph(f"答：{item.get('answer', '')}", styles["BodyText"]))
        story.append(Spacer(1, 0.2 * cm))

    doc.build(story)
    return buffer.getvalue()

# UI部
st.set_page_config(page_title="学習用PDF生成アプリ", layout="centered")

st.title("📚 ClearPDF")
st.write("講義PDFを読み込み、認知的ノイズを抑えたシンプルな学習ガイドPDFを出力します。")

uploaded_file = st.file_uploader("PDFファイルをアップロード", type=["pdf"])

if uploaded_file is not None:
    if st.button("PDFを生成する", type="primary"):
        with st.spinner("テキストの抽出・構造化を行っています..."):
            try:
                pdf_bytes = uploaded_file.read()
                raw_text = extract_text_from_pdf(pdf_bytes)
                study_data = generate_study_data(raw_text)
                output_pdf_bytes = render_pdf(study_data)

                # PDFのダウンロード用状態保持
                st.session_state["pdf_data"] = output_pdf_bytes
                st.session_state["file_name"] = (
                    f"Minimal_Study_{uploaded_file.name}"
                )
                st.success("PDFの生成が完了しました！")

            except Exception as e:
                st.error(f"エラーが発生しました: {str(e)}")

# PDFが生成されている場合、右からスライドイン表示
if "pdf_data" in st.session_state:
    st.download_button(
        label="📥 生成されたPDFをダウンロード",
        data=st.session_state["pdf_data"],
        file_name=st.session_state["file_name"],
        mime="application/pdf",
    )

    # Base64エンコードして<iframe>に渡す
    base64_pdf = base64.b64encode(st.session_state["pdf_data"]).decode("utf-8")

    # 右から湧き上がる（スライドイン＆フェードイン）CSSとHTML
        # PDF.js を使用して安全にレンダリングするHTML/CSSコード
    preview_html = f"""
    <div id="pdf-container" class="pdf-preview-container">
        <canvas id="pdf-render"></canvas>
    </div>

    <style>
    @keyframes slideInRight {{
        0% {{
            transform: translateX(100%) scale(0.9);
            opacity: 0;
        }}
        100% {{
            transform: translateX(0) scale(1);
            opacity: 1;
        }}
    }}
    .pdf-preview-container {{
        animation: slideInRight 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        border-radius: 12px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        margin-top: 20px;
        background-color: #525659;
        display: flex;
        justify-content: center;
        padding: 20px 0;
        max-height: 600px;
        overflow-y: auto;
    }}
    #pdf-render {{
        border: 1px solid #ccc;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }}
    </style>

    <!-- PDF.js CDN -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
    <script>
    const pdfData = atob("{base64_pdf}");
    const loadingTask = pdfjsLib.getDocument({{data: pdfData}});
    
    loadingTask.promise.then(pdf => {{
        // 1ページ目をレンダリング
        pdf.getPage(1).then(page => {{
            const viewport = page.getViewport({{scale: 1.2}});
            const canvas = document.getElementById('pdf-render');
            const context = canvas.getContext('2d');
            canvas.height = viewport.height;
            canvas.width = viewport.width;

            const renderContext = {{
                canvasContext: context,
                viewport: viewport
            }};
            page.render(renderContext);
        }});
    }}).catch(err => {{
        console.error("PDF.js Render Error: ", err);
    }});
    </script>
    """

    st.components.v1.html(preview_html, height=650)
