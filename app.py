"""AI Study Notes & Quiz Generator — Streamlit entry point."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader


APP_TITLE = "AI Study Notes & Quiz Generator"
DEVELOPER = "Pritam Kumar Mandal"
MODEL_NAME = "gemini-3.8-flash"  # Change this one value to switch Gemini models.
MAX_INPUT_CHARACTERS = 60_000
MAX_UPLOAD_BYTES = 15 * 1024 * 1024

QUIZ_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "questions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "question": {"type": "STRING"},
                    "options": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "correct_answer": {"type": "STRING"},
                    "explanation": {"type": "STRING"},
                },
                "required": ["question", "options", "correct_answer", "explanation"],
            },
        }
    },
    "required": ["questions"],
}

FLASHCARD_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "flashcards": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"front": {"type": "STRING"}, "back": {"type": "STRING"}},
                "required": ["front", "back"],
            },
        }
    },
    "required": ["flashcards"],
}


def get_api_key() -> str | None:
    """Read a key from the environment or Streamlit secrets without exposing it."""
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key.strip()
    try:
        value = st.secrets.get("GEMINI_API_KEY")
        return str(value).strip() if value else None
    except (FileNotFoundError, KeyError, AttributeError):
        return None


def extract_pdf_text(uploaded_file: Any) -> str:
    """Extract selectable text from a PDF and explain common extraction failures."""
    try:
        reader = PdfReader(uploaded_file)
        if reader.is_encrypted:
            raise ValueError("This PDF is password-protected. Upload an unlocked copy.")
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(part.strip() for part in pages if part.strip()).strip()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("We could not read this PDF. Check that it is a valid, unencrypted PDF.") from exc
    if not text:
        raise ValueError("No selectable text was found. This may be a scanned PDF; use OCR first or paste its text.")
    return text


def read_uploaded_file(uploaded_file: Any) -> str:
    """Read a supported TXT or PDF upload while enforcing a file-size limit."""
    if uploaded_file.size > MAX_UPLOAD_BYTES:
        raise ValueError("That file is larger than 15 MB. Choose a smaller file.")
    suffix = os.path.splitext(uploaded_file.name)[1].lower()
    if suffix == ".pdf":
        return extract_pdf_text(uploaded_file)
    if suffix == ".txt":
        try:
            text = uploaded_file.getvalue().decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("This TXT file is not UTF-8 encoded. Save it as UTF-8 and try again.") from exc
        if not text:
            raise ValueError("This TXT file is empty. Upload a file that contains study material.")
        return text
    raise ValueError("Unsupported file type. Upload a PDF or TXT file.")


def make_client() -> genai.Client:
    key = get_api_key()
    if not key:
        raise RuntimeError("Gemini API key is missing. Add GEMINI_API_KEY in your environment or Streamlit secrets.")
    return genai.Client(api_key=key)


def generate_text(prompt: str, *, schema: dict[str, Any] | None = None) -> str:
    """Call Gemini without caching user documents; return generated text."""
    config = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json" if schema else "text/plain",
        response_schema=schema,
    )
    response = make_client().models.generate_content(model=MODEL_NAME, contents=prompt, config=config)
    result = response.text
    if not result or not result.strip():
        raise ValueError("Gemini returned an empty response. Please try again.")
    return result.strip()


def generate_notes(material: str) -> str:
    prompt = f"""Create faithful study notes using ONLY the source below. Do not add outside facts or infer unsupported details.
Use clear Markdown headings and concise bullets. Highlight key terms in **bold**. Include important concepts, definitions, and facts, then finish with a heading 'Quick Revision' and a short revision summary.

SOURCE MATERIAL:
{material}"""
    return generate_text(prompt)


def validate_quiz_data(data: Any, requested_count: int) -> list[dict[str, Any]]:
    """Keep only unique, well-formed questions with exactly four valid options."""
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise ValueError("The quiz response did not contain a question list. Try generating it again.")
    valid: list[dict[str, Any]] = []
    seen_questions: set[str] = set()
    for item in data["questions"]:
        if not isinstance(item, dict):
            continue
        question = item.get("question")
        options = item.get("options")
        answer = item.get("correct_answer")
        explanation = item.get("explanation")
        if not all(isinstance(value, str) and value.strip() for value in (question, answer, explanation)):
            continue
        if not isinstance(options, list) or len(options) != 4 or not all(isinstance(opt, str) and opt.strip() for opt in options):
            continue
        options = [opt.strip() for opt in options]
        if len({opt.casefold() for opt in options}) != 4:
            continue
        matching = [opt for opt in options if opt.casefold() == answer.strip().casefold()]
        if len(matching) != 1:
            continue
        normalized_question = re.sub(r"\W+", " ", question).strip().casefold()
        if normalized_question in seen_questions:
            continue
        seen_questions.add(normalized_question)
        valid.append({"question": question.strip(), "options": options,
                      "correct_answer": matching[0], "explanation": explanation.strip()})
        if len(valid) == requested_count:
            break
    return valid


def generate_quiz(material: str, count: int) -> list[dict[str, Any]]:
    prompt = f"""Create up to {count} distinct multiple-choice questions based only on the source. Aim for {count} questions. Each must test a meaningful point, have four distinct plausible options, exactly one correct option, and a brief explanation grounded in the source. Do not include unsupported facts. Return fewer only if the source cannot support more valid questions.

SOURCE MATERIAL:
{material}"""
    raw = generate_text(prompt, schema=QUIZ_SCHEMA)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini returned malformed quiz data. Please generate the quiz again.") from exc
    return validate_quiz_data(data, count)


def validate_flashcards(data: Any) -> list[dict[str, str]]:
    if not isinstance(data, dict) or not isinstance(data.get("flashcards"), list):
        raise ValueError("The flashcard response was not in the expected format. Try again.")
    result = []
    seen = set()
    for card in data["flashcards"]:
        if not isinstance(card, dict):
            continue
        front, back = card.get("front"), card.get("back")
        if not isinstance(front, str) or not front.strip() or not isinstance(back, str) or not back.strip():
            continue
        if front.strip().casefold() in seen:
            continue
        seen.add(front.strip().casefold())
        result.append({"front": front.strip(), "back": back.strip()})
    return result


def generate_flashcards(material: str) -> list[dict[str, str]]:
    prompt = f"Create 8 to 12 concise study flashcards using only the source material. Put a clear question or term on each front and its answer or definition on the back. Do not invent facts.\n\nSOURCE MATERIAL:\n{material}"
    raw = generate_text(prompt, schema=FLASHCARD_SCHEMA)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini returned malformed flashcard data. Please try again.") from exc
    return validate_flashcards(data)


def score_quiz(questions: list[dict[str, Any]], answers: dict[int, str]) -> tuple[int, float]:
    correct = sum(answers.get(index, "").casefold() == q["correct_answer"].casefold()
                  for index, q in enumerate(questions))
    percentage = (correct / len(questions) * 100) if questions else 0.0
    return correct, percentage


def load_input() -> str:
    """Combine pasted text with an optional upload and keep source in session state."""
    pasted = st.session_state.get("pasted_material", "").strip()
    uploaded = st.session_state.get("study_file")
    file_text = ""
    if uploaded is not None:
        try:
            file_text = read_uploaded_file(uploaded)
        except ValueError as exc:
            st.error(str(exc))
            return ""
    if pasted and file_text:
        material = f"{pasted}\n\n{file_text}"
    else:
        material = pasted or file_text
    if len(material) > MAX_INPUT_CHARACTERS:
        st.error(f"Your combined material has {len(material):,} characters. The limit is {MAX_INPUT_CHARACTERS:,}; shorten it before generating content.")
        return ""
    st.session_state["study_material"] = material
    return material


st.set_page_config(page_title=APP_TITLE, page_icon="📘", layout="wide")
st.markdown("""
<style>
  .stApp { background: #f5f7fb; color: #14233b; }
  [data-testid="stSidebar"] { background: #102443; }
  [data-testid="stSidebar"] * { color: #f4f7ff; }
  .hero { padding: 1.5rem 1.8rem; border-radius: 18px; color: white;
    background: linear-gradient(115deg,#102443,#1e4b83); margin-bottom: 1rem; }
  .hero h1 { color: white; margin: 0; }
  .hero p { color: #d8e6fb; margin: .35rem 0 0; }
  .metric-card { background:white; padding:1rem 1.2rem; border-radius:14px;
    border:1px solid #e4eaf3; box-shadow:0 3px 14px #13294b0a; }
  .metric-label { color:#64748b; font-size:.88rem; }
  .metric-value { color:#102443; font-size:1.4rem; font-weight:700; }
  footer { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 📘 Study Studio")
    st.write("**How to use**")
    st.markdown("1. Paste notes or upload a PDF/TXT.\n2. Choose Notes, Quiz, or Flashcards.\n3. Generate and save your revision materials.")
    st.divider()
    if get_api_key():
        st.success("Gemini API key configured")
    else:
        st.warning("Gemini API key not configured")
    st.caption(f"Model: `{MODEL_NAME}`")
    st.divider()
    st.write("**Project**")
    st.caption("AI Study Notes & Quiz Generator")
    st.caption(f"Created by {DEVELOPER}")
    st.markdown("[GitHub: @Pritam2005D](https://github.com/Pritam2005D)")

st.markdown(f'<div class="hero"><h1>{APP_TITLE}</h1><p>Turn your study material into notes, quizzes, and flashcards.</p></div>', unsafe_allow_html=True)

input_col, stats_col = st.columns([2.2, 1])
with input_col:
    st.text_area("Paste study material", key="pasted_material", height=190,
                 placeholder="Paste lecture notes, textbook extracts, or study material here…")
    st.file_uploader("Or upload a PDF or TXT file", type=["pdf", "txt"], key="study_file",
                     help="Maximum file size: 15 MB. Scanned PDFs need OCR before upload.")
    material = load_input()
with stats_col:
    char_count = len(material)
    st.markdown(f'<div class="metric-card"><div class="metric-label">Extracted text</div><div class="metric-value">{char_count:,} characters</div><div class="metric-label">Limit: {MAX_INPUT_CHARACTERS:,}</div></div>', unsafe_allow_html=True)
    st.progress(min(char_count / MAX_INPUT_CHARACTERS, 1.0))
    st.caption("Your document is sent to Gemini only when you choose to generate content. It is not cached by this app.")

notes_tab, quiz_tab, cards_tab = st.tabs(["📝 Notes", "✅ Quiz", "🗂️ Flashcards"])

with notes_tab:
    st.subheader("AI Study Notes")
    if st.button("Generate Study Notes", type="primary", key="generate_notes", disabled=not bool(material)):
        try:
            with st.spinner("Turning your material into concise study notes…"):
                st.session_state["notes"] = generate_notes(material)
        except Exception as exc:
            st.error(f"Could not generate notes: {exc}")
    if st.session_state.get("notes"):
        st.markdown(st.session_state["notes"])
        st.download_button("Download notes (.md)", st.session_state["notes"], "study_notes.md", "text/markdown")
        st.download_button("Download notes (.txt)", st.session_state["notes"], "study_notes.txt", "text/plain")

with quiz_tab:
    st.subheader("Interactive Quiz")
    requested_count = st.selectbox("Number of questions", [5, 10, 15], key="requested_quiz_count")
    if st.button("Generate Quiz", type="primary", key="generate_quiz", disabled=not bool(material)):
        try:
            with st.spinner("Creating and checking your questions…"):
                generated = generate_quiz(material, requested_count)
            for old_index in range(len(st.session_state.get("quiz_questions", []))):
                st.session_state.pop(f"answer_{old_index}", None)
            st.session_state["quiz_questions"] = generated
            st.session_state["quiz_answers"] = {}
            st.session_state["quiz_submitted"] = False
            st.session_state["quiz_feedback"] = None
            if generated and len(generated) < requested_count:
                st.info(f"The source supported {len(generated)} valid questions out of {requested_count} requested.")
            elif not generated:
                st.warning("The source did not produce valid questions. Try adding more study material.")
        except Exception as exc:
            st.error(f"Could not generate a quiz: {exc}")

    questions = st.session_state.get("quiz_questions", [])
    if questions:
        st.caption(f"{len(questions)} questions · Select one answer for each, then submit.")
        answers: dict[int, str] = st.session_state.setdefault("quiz_answers", {})
        for index, question in enumerate(questions):
            st.markdown(f"**{index + 1}. {question['question']}**")
            chosen = st.radio("Choose an answer", question["options"], key=f"answer_{index}",
                              index=None, label_visibility="collapsed", disabled=st.session_state.get("quiz_submitted", False))
            if chosen is not None:
                answers[index] = chosen
        if not st.session_state.get("quiz_submitted", False):
            if st.button("Submit Quiz", type="primary", key="submit_quiz"):
                if len(answers) != len(questions):
                    st.warning("Answer every question before submitting.")
                else:
                    st.session_state["quiz_submitted"] = True
                    st.rerun()
        else:
            correct, percentage = score_quiz(questions, answers)
            st.success(f"Score: {correct} / {len(questions)} · {percentage:.0f}%")
            st.progress(percentage / 100)
            for index, question in enumerate(questions):
                chosen = answers.get(index, "")
                is_correct = chosen.casefold() == question["correct_answer"].casefold()
                st.markdown(f"**{index + 1}. {'✅ Correct' if is_correct else '❌ Incorrect'}**")
                if not is_correct:
                    st.write(f"Your answer: {chosen} · Correct answer: {question['correct_answer']}")
                st.caption(question["explanation"])
            quiz_export = {"questions": questions}
            st.download_button("Download quiz (.json)", json.dumps(quiz_export, indent=2, ensure_ascii=False),
                               "study_quiz.json", "application/json")
            if st.button("Restart Quiz", key="restart_quiz"):
                for index in range(len(questions)):
                    st.session_state.pop(f"answer_{index}", None)
                st.session_state["quiz_answers"] = {}
                st.session_state["quiz_submitted"] = False
                st.rerun()

with cards_tab:
    st.subheader("Flashcards")
    if st.button("Generate Flashcards", type="primary", key="generate_flashcards", disabled=not bool(material)):
        try:
            with st.spinner("Making a focused set of flashcards…"):
                st.session_state["flashcards"] = generate_flashcards(material)
            st.session_state["flashcard_index"] = 0
            st.session_state["flashcard_revealed"] = False
        except Exception as exc:
            st.error(f"Could not generate flashcards: {exc}")
    cards = st.session_state.get("flashcards", [])
    if cards:
        index = st.session_state.get("flashcard_index", 0)
        card = cards[index]
        st.caption(f"Card {index + 1} of {len(cards)}")
        st.markdown(f"### {card['front']}")
        if st.button("Hide answer" if st.session_state.get("flashcard_revealed") else "Reveal answer", key="reveal_card"):
            st.session_state["flashcard_revealed"] = not st.session_state.get("flashcard_revealed", False)
        if st.session_state.get("flashcard_revealed"):
            st.info(card["back"])
        previous, next_col = st.columns(2)
        with previous:
            if st.button("← Previous", disabled=index == 0, key="previous_card"):
                st.session_state["flashcard_index"] = index - 1
                st.session_state["flashcard_revealed"] = False
                st.rerun()
        with next_col:
            if st.button("Next →", disabled=index == len(cards) - 1, key="next_card"):
                st.session_state["flashcard_index"] = index + 1
                st.session_state["flashcard_revealed"] = False
                st.rerun()

st.markdown("<br><hr><center style='color:#64748b'>Built for focused learning · Pritam Kumar Mandal · <a href='https://github.com/Pritam2005D' target='_blank' rel='noopener noreferrer'>GitHub</a></center>", unsafe_allow_html=True)
