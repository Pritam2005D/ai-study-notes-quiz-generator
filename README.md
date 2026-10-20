# AI Study Notes & Quiz Generator

A Streamlit learning dashboard that turns your own study text into concise revision notes, multiple-choice quizzes, and flashcards using Google's Gemini API. PDF text is extracted locally with PyPDF before you choose to send material to Gemini.

**Developer:** Pritam Kumar Mandal<br>
**GitHub:** [@Pritam2005D](https://github.com/Pritam2005D)<br>
**Stack:** Python, Streamlit, Google GenAI SDK, PyPDF

## Features

- Paste notes or upload a PDF/TXT document (15 MB maximum).
- See the extracted text length and stay within the 60,000 character request limit.
- Generate structured notes with headings, key terms, and a Quick Revision summary.
- Create 5, 10, or 15 validated quiz questions; answer them and see the score, correct answers, and explanations after submission.
- Make and navigate simple question-and-answer flashcards.
- Download notes as Markdown/TXT and a completed quiz as JSON.
- Keep the Gemini key outside the source code using an environment variable or Streamlit secret.

The app does not cache study documents. Documents are sent to Gemini only when a generation button is selected. The AI must stick to the supplied material, but generated content can still be inaccurate; check important facts against your source.

## Requirements

- Python 3.10 or newer.
- A Gemini API key for AI generation. The app itself can start without a key; generation then displays setup guidance.
- Internet access when calling Gemini.

Google's free API access, quotas, pricing, and available models can change. `MODEL_NAME` is defined near the top of `app.py` so it is easy to update. Check Google's current [Gemini model list](https://ai.google.dev/gemini-api/docs/models) if the configured model is unavailable to your account.

## Setup on Windows

Open this project folder in VS Code, then open **Terminal → New Terminal**. In PowerShell, create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, use Command Prompt in VS Code and run:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the app from the project folder:

```powershell
streamlit run app.py
```

Streamlit will show a local URL (usually `http://localhost:8501`) and open it in your browser. Stop the server with **Ctrl+C** in the terminal.

## Configure the Gemini key safely

Create a key from [Google AI Studio](https://aistudio.google.com/apikey). Never paste a real key into `app.py`, README, screenshots, or GitHub.

### Local environment variable (PowerShell)

Set it for the current terminal session, then start Streamlit from that same terminal:

```powershell
$env:GEMINI_API_KEY = "paste-your-key-here"
streamlit run app.py
```

The variable disappears when that terminal closes. For repeat local use, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, replace the placeholder with your key, and run `streamlit run app.py`. `secrets.toml` is excluded by `.gitignore`; do not commit it.

If Gemini returns `API_KEY_INVALID`, create a replacement key in [Google AI Studio](https://aistudio.google.com/apikey), update the local secret or Streamlit Cloud app's **Settings → Secrets**, and restart the app. Do not reuse a key that has been shared in chat.

In PowerShell, the copy command is:

```powershell
Copy-Item .streamlit/secrets.toml.example .streamlit/secrets.toml
```

## GitHub upload

On GitHub, create an empty public repository under [@Pritam2005D](https://github.com/Pritam2005D) named `ai-study-notes-quiz-generator`. Do not initialize it with a README or license. Then run these commands from this project folder:

```powershell
git init
git add app.py requirements.txt README.md .gitignore .streamlit/secrets.toml.example
git commit -m "Build AI study notes and quiz generator"
git branch -M main
git remote add origin https://github.com/Pritam2005D/ai-study-notes-quiz-generator.git
git push -u origin main
```

Before pushing, check `git status` and make sure `.streamlit/secrets.toml`, `.env`, and any real key are not staged. The example file contains only a placeholder.

## Deploy to Streamlit Community Cloud

1. Push the project to a GitHub repository.
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) and choose **Create app**.
3. Select the repository, branch (`main`), and app file (`app.py`), then deploy.
4. In the app's settings, open **Secrets** and add:

   ```toml
   GEMINI_API_KEY = "paste-your-key-here"
   ```

5. Save the secret and allow the app to restart. Keep it in Cloud secrets, not in GitHub files.

## How the AI workflow works

1. The app reads pasted text or extracts selectable PDF text with PyPDF. It checks the file and text-size limits before generation.
2. When a user chooses a feature, the app sends the source material with a task-specific instruction to Gemini using the official `google-genai` SDK.
3. Notes are returned as Markdown. Quiz and flashcard requests ask Gemini for JSON; quiz questions are checked for four unique options, exactly one answer matching the key, required explanations, and duplicate questions.
4. Quiz scoring is ordinary Python comparison against the validated answer key. The key and explanations are only displayed after submission.

This is a direct generation workflow, not a search index or offline model. A configured key and network connection are needed for generation.

## Limitations

- Scanned/image-only PDFs need OCR before upload; this app extracts selectable text only.
- Source material is limited to 60,000 characters per generation and uploads to 15 MB.
- Long or sparse source material may yield fewer valid quiz questions than requested.
- Gemini output may contain mistakes even with source-grounded prompts and validation. Review the notes and quiz before relying on them.
- Google API quotas, free access, model names, and availability are controlled by Google and can change.

## Files

- `app.py` — Streamlit UI, input processing, Gemini generation, validation, quiz scoring, downloads.
- `requirements.txt` — Python dependencies.
- `.streamlit/secrets.toml.example` — safe local secret template.
- `.gitignore` — excludes secrets, virtual environments, and common generated files.
