# app.py
from typing import Optional, Annotated, List
import io
import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from PyPDF2 import PdfReader
from openai import OpenAI
import httpx  # <-- we hand OpenAI a proxy-free client

app = FastAPI(title="Jigsaw Annotator (No-Proxy)")
log = logging.getLogger("uvicorn.error")

# ---------------------------
# Models & helpers
# ---------------------------
class JigsawPayload(BaseModel):
    topic: str
    student_name: Optional[str] = None
    notes_style: str = "bulleted"

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from the PDF using PyPDF2."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts: List[str] = []
        for p in reader.pages:
            t = (p.extract_text() or "").strip()
            if t:
                parts.append(t)
        text = "\n\n".join(parts).strip()
        if not text:
            raise ValueError("No extractable text found (scanned PDF?).")
        return text
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"PDF text extraction failed: {e}")

def chunk(text: str, max_chars: int = 8000) -> List[str]:
    text = text.strip()
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

async def make_notes(topic: str, notes_style: str, student_name: Optional[str], text: str, client):
    style_map = {
        "bulleted": "Return clear bullet points. Include sub-bullets as needed to appear natural.",
        "outline": "Return an outline using I., A., 1., a. structure.",
        "summary": "Return a concise multi-paragraph summary highlighting main ideas and definitions."
    }
    system = "You are a high school student completing a jigsaw research assignment. Parse the provided document and return notes formatted for Google Docs based on the selected style (bulleted, outline, summary, etc.) Your notes should be on the various articles provided in the PDF. If you are unable to access any of the articles, return 'Unable to access source.' where you would have put notes. You should return between seven and ten lines of notes for each source (whether that's bullet points, outlines, etc.), depending on how long the source is. Write notes summarizing the source. Use natural formatting for informal notes of this form; for instance, have variation in what is capitalized and punctuation. It should appear to be written naturally by a highschooler."

    def call_model(prompt: str) -> str:
        # Try the new Responses API first; if not available, use Chat Completions.
        try:
            resp = client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.output_text
        except AttributeError:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            return resp.choices[0].message.content

    outs = []
    for i, piece in enumerate(chunk(text)):
        prompt = (
            f"Topic: {topic}\n"
            f"Student: {student_name or 'N/A'}\n"
            f"Desired style: {notes_style}\n"
            f"Instructions: {style_map.get(notes_style, style_map['bulleted'])}\n\n"
            f"Source text (part {i+1}):\n{piece}"
        )
        outs.append(call_model(prompt))

    return "\n\n".join(outs).strip()
    style_map = {
        "bulleted": "Return clear bullet points with sub-bullets as needed.",
        "outline": "Return an outline using I., A., 1., a. structure.",
        "summary": "Return a concise multi-paragraph summary highlighting main ideas and definitions."
    }
    system = "You are a helpful study assistant. Extract key ideas and produce concise, accurate notes."

    outputs: List[str] = []
    for i, piece in enumerate(chunk(text)):
        prompt = (
            f"Topic: {topic}\n"
            f"Student: {student_name or 'N/A'}\n"
            f"Desired style: {notes_style}\n"
            f"Instructions: {style_map.get(notes_style, style_map['bulleted'])}\n\n"
            f"Source text (part {i+1}):\n{piece}"
        )
        resp = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        outputs.append(resp.output_text)
    return "\n\n".join(outputs).strip()

# ---------------------------
# Error handlers → always JSON
# ---------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": "validation_error", "detail": exc.errors()})

@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": "http_error", "detail": exc.detail})

@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": "server_error", "detail": str(exc)})

# ---------------------------
# Frontend
# ---------------------------
@app.get("/", response_class=HTMLResponse)
async def upload_form():
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8"/>
      <title>Upload Jigsaw Assignment PDF</title>
      <style>
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
        h1 { font-size: 2rem; margin-bottom: 1rem; }
        form { margin-top: 1rem; }
        form > div { margin: 0.75rem 0; }
        input[type="text"], input[type="text"], select { padding: 0.45rem 0.6rem; width: 420px; }
        input[type="file"] { padding: 0.2rem 0; }
        button { padding: 0.7rem 1.1rem; border-radius: 10px; border: 1px solid #222; background: #222; color: #fff; cursor: pointer; }
        pre#out { white-space: pre-wrap; border: 1px solid #ddd; padding: 1rem; border-radius: 8px; margin-top: 1.25rem; }
        .muted { color: #666; font-size: 0.9rem; margin-top: 0.5rem; }
      </style>
    </head>
    <body>
      <h1>Upload Jigsaw Assignment PDF</h1>
      <form id="jigsaw-form" action="/jigsaw/annotate" method="post" enctype="multipart/form-data">
        <div>
          <label>Topic</label><br/>
          <input type="text" name="topic" required />
        </div>
        <div>
          <label>Student Name</label><br/>
          <input type="text" name="student_name" />
        </div>
        <div>
          <label>Notes Style</label><br/>
          <select name="notes_style">
            <option value="bulleted">Bulleted</option>
            <option value="outline">Outline</option>
            <option value="summary">Summary</option>
          </select>
        </div>
        <div>
          <label>Upload PDF</label><br/>
          <input type="file" name="pdf" accept=".pdf" required />
        </div>
        <div>
          <label>OpenAI API Key</label><br/>
          <input type="text" name="openai_key" placeholder="sk-..." required />
        </div>
        <button type="submit">Generate Notes</button>
        <div class="muted">Your key is used only for this request and not stored.</div>
      </form>

      <pre id="out"></pre>

      <script>
        const form = document.getElementById('jigsaw-form');
        const outEl = document.getElementById('out');

        form.addEventListener('submit', async (e) => {
          e.preventDefault();
          outEl.textContent = "Working…";
          const res = await fetch('/jigsaw/annotate', { method: 'POST', body: new FormData(form) });
          const raw = await res.text();

          if (!res.ok) {
            try {
              const err = JSON.parse(raw);
              outEl.textContent = `Error ${res.status} (${err.error || "server"}): ${err.detail || raw}`;
            } catch {
              outEl.textContent = `Error ${res.status}: ${raw}`;
            }
            return;
          }

          const json = JSON.parse(raw);
          outEl.textContent = json.notes || JSON.stringify(json, null, 2);
        });
      </script>
    </body>
    </html>
    """

# ---------------------------
# API
# ---------------------------
@app.post("/jigsaw/annotate")
async def annotate_jigsaw(
    topic: Annotated[str, Form(...)],
    pdf: Annotated[UploadFile, File(..., description="Upload a PDF of the jigsaw assignment")],
    openai_key: Annotated[str, Form(...)],
    student_name: Annotated[Optional[str], Form()] = None,
    notes_style: Annotated[str, Form()] = "bulleted",
):
    if pdf.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Build a proxy-free HTTP client so env proxies are ignored.
    # trust_env=False => ignore HTTP_PROXY/HTTPS_PROXY/etc entirely.
    http_client = httpx.Client(timeout=60, trust_env=False)

    # Create the OpenAI client with ONLY the api_key and our http_client.
    client = OpenAI(api_key=openai_key, http_client=http_client)

    # Extract text from the PDF
    pdf_bytes = await pdf.read()
    text = extract_pdf_text(pdf_bytes)

    # Generate notes
    notes = await make_notes(topic=topic, notes_style=notes_style, student_name=student_name, text=text, client=client)

    return JSONResponse({
        "received": {"filename": pdf.filename, "n_bytes": len(pdf_bytes), "content_type": pdf.content_type},
        "payload": JigsawPayload(topic=topic, student_name=student_name, notes_style=notes_style).model_dump(),
        "notes": notes
    })