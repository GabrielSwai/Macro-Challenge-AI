# Macro‑Challenge‑AI — Jigsaw PDF → Notes

A tiny FastAPI app that takes a **PDF jigsaw assignment** and returns **clean notes** with OpenAI.
Paste your own API key on the page. Nothing is stored.

---

## Quickstart

```bash
# 1) create a virtual env
python3 -m venv .venv && source .venv/bin/activate

# 2) install deps
pip install -r requirements.txt

# 3) run the server
uvicorn app:app --reload --port 8000

# 4) open the app
open http://127.0.0.1:8000/
```

---

## How to use (browser)

1. Enter a **Topic** and (optionally) **Student Name**.  
2. Pick a **Notes Style** (Bulleted / Outline / Summary).  
3. Select a **.pdf** file.  
4. Paste your **OpenAI API key** (`sk-...`).  
5. Click **Generate Notes** — results appear under the form.

Your key is used only for this single request.

---

## API (cURL)

`POST /jigsaw/annotate` (multipart form)

- `topic` (str, required)  
- `pdf` (file, required)  
- `openai_key` (str, required)  
- `student_name` (str, optional)  
- `notes_style` (str, optional: `bulleted` | `outline` | `summary`, default `bulleted`)

```bash
curl -X POST http://127.0.0.1:8001/jigsaw/annotate   -F "topic=Photosynthesis"   -F "student_name=Alex"   -F "notes_style=outline"   -F "openai_key=$OPENAI_API_KEY"   -F "pdf=@/path/to/jigsaw.pdf;type=application/pdf"
```

---

## Notes

- Text extraction uses **PyPDF2**. If your PDF is a **scan** (no text layer), add OCR later (e.g., `pytesseract + pdf2image`).  
- The app supplies a **proxy‑free** HTTP client so corporate proxy env vars won’t break the OpenAI SDK.  
- Works with the modern OpenAI SDK; if `responses` API isn’t available in your version, the app falls back to **chat completions**.

---

## Troubleshooting

- **401/403 from OpenAI** → bad/expired key or project/org restrictions.  
- **“No extractable text found”** → scanned PDF; add OCR.  
- **Can’t reach server** → make sure `uvicorn` is running on `:8000` and no firewall is blocking it.

---

👤 Built & maintained by [Gabriel Swai](https://gabrielswai.com).
