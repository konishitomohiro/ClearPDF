import streamlit as st
import fitz  # PyMuPDF
import json
import os
from google import genai
from google.genai import types
from jinja2 import Template
from weasyprint import HTML

# ---------------------------------------------------------
# 視覚・認知の最適化を施したHTML/CSSテンプレート
# ノイズ削減のため：色分け廃止、枠線廃止、カードデザイン廃止
# ---------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');
    @page { 
      size: A4; 
      margin: 25mm 20mm; /* タブレット筆記・余白確保のための広めマージン */
    }
    body { 
      font-family: "Noto Sans JP", "Hiragino Sans", "Meiryo", Arial, sans-serif; 
      color: #000000; /* 完全な白黒で視覚刺激を統一 */
      line-height: 1.8; /* 行間を広げて読書負荷を軽減 */
      font-size: 11pt;
    }
    
    /* 項目（タイトル）の見出し構造 */
    h1 { 
      font-size: 18pt; 
      font-weight: bold;
      margin-bottom: 24pt;
      padding-bottom: 6pt;
      border-bottom: 1px solid #000000; /* 単純な黒の下線のみ */
      font-family: "Noto Sans JP", "Hiragino Sans", "Meiryo", Arial, sans-serif;
    }
    h2 { 
      font-size: 14pt; 
      font-weight: bold;
      margin-top: 28pt; 
      margin-bottom: 12pt;
      font-family: "Noto Sans JP", "Hiragino Sans", "Meiryo", Arial, sans-serif;
    }
    
    /* 本文・リストのノイズ削減 */
    p { 
      margin-bottom: 10pt; 
    }
    ul, ol { 
      padding-left: 20pt; 
      margin-bottom: 14pt; 
    }
    li { 
      margin-bottom: 6pt; 
    }
    
    /* 太字（キーワード）の強調も最小限に */
    .term { 
      font-weight: bold; 
    }
    
    /* クイズセクション（カードや枠線を完全廃止し、シンプルな段落へ） */
    .quiz-item {
      margin-bottom: 16pt;
    }
    .question {
      font-weight: bold;
    }
    .answer {
      margin-top: 4pt;
      color: #333333; /* 回答であることが分かる最小限のトーン差 */
    }
  </style>
</head>
<body>
  <h1>{{ data.title }}</h1>

  <h2>1. 重要用語と解説</h2>
  {% for item in data.key_terms %}
    <p><span class="term">{{ item.term }}</span>：{{ item.definition }}</p>
  {% endfor %}

  <h2>2. 講義要点・概念</h2>
  <ul>
    {% for point in data.core_points %}
      <li>{{ point }}</li>
    {% endfor %}
  </ul>

  <h2>3. セルフチェック問題</h2>
  {% for q in data.quiz %}
    <div class="quiz-item">
      <div class="question">問：{{ q.question }}</div>
      <div class="answer">答：{{ q.answer }}</div>
    </div>
  {% endfor %}
</body>
</html>
"""

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    return "\n".join([page.get_text() for page in doc])

def generate_study_data(text: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません。")

    client = genai.Client(api_key=api_key)
    prompt = f"以下の講義テキストを解析し、構造化された試験対策テキストを作成してください:\n\n{text[:10000]}"

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
    template = Template(HTML_TEMPLATE)
    html_out = template.render(data=data)
    return HTML(string=html_out).write_pdf()

# UI部
st.set_page_config(page_title="学習用PDF生成アプリ", layout="centered")

st.title("📚 ミニマル学習PDFジェネレーター")
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

                st.success("PDFの生成が完了しました！")
                st.download_button(
                    label="📥 生成されたPDFをダウンロード",
                    data=output_pdf_bytes,
                    file_name=f"Minimal_Study_{uploaded_file.name}",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"エラーが発生しました: {str(e)}")
