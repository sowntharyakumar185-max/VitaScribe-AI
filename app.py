from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, make_response
import os
from datetime import datetime
from generate_pdf import create_pdf
from clean_text import clean_text
from summarize_text import summarize_text
from dotenv import load_dotenv
from deep_translator import GoogleTranslator
import re
import difflib

import glob
import smtplib
from email.message import EmailMessage

import subprocess

from database import (
    init_db,
    save_visit,
    update_visit_language,
    update_visit_contact_email,
    get_stats,
    get_recent_visits,
    get_clinic_info,
    get_medical_terms,
    upsert_medical_term,
    delete_medical_term,
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

# Simple user login (before main page)
APP_USERNAME = os.getenv("APP_USERNAME", "user")
APP_PASSWORD = os.getenv("APP_PASSWORD", "user123")

init_db()

latest_pdf = None

UPLOAD_FOLDER = "static/recordings"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# -------------------- WHISPER MODEL --------------------
model = None

def get_model():
    global model
    if model is None:
        try:
            whisper_module = __import__("whisper")
            # Higher default accuracy for word-level recognition.
            # You can still override with env WHISPER_MODEL=tiny/base/small/medium etc.
            model_name = os.getenv("WHISPER_MODEL", "medium")
            model = whisper_module.load_model(model_name)
        except Exception as e:
            raise RuntimeError(f"Failed to load Whisper model: {e}")
    return model


# -------------------- AUDIO PROCESSING --------------------
def convert_audio(input_path, output_path):
    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ar", "16000",
        "-ac", "1",
        output_path
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=25,
    )
    return result.returncode == 0 and os.path.exists(output_path)


def enhance_audio_for_speech(input_path, output_path):
    """
    Apply light denoise + normalization to improve recognition on unclear speech.
    """
    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-af", "highpass=f=100,lowpass=f=7000,afftdn,loudnorm",
        "-ar", "16000",
        "-ac", "1",
        output_path
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )
    return result.returncode == 0 and os.path.exists(output_path)


def pick_better_transcription(result_a, result_b):
    """
    Choose the better Whisper output using simple confidence heuristics.
    """
    def confidence(result):
        text = (result or {}).get("text", "").strip()
        if not text:
            return -9999.0

        segments = (result or {}).get("segments", []) or []
        if not segments:
            return float(len(text)) * 0.01

        avg_logprob_sum = 0.0
        no_speech_sum = 0.0
        seg_count = 0

        for seg in segments:
            avg_logprob_sum += float(seg.get("avg_logprob", -2.0))
            no_speech_sum += float(seg.get("no_speech_prob", 1.0))
            seg_count += 1

        if seg_count == 0:
            return float(len(text)) * 0.01

        avg_logprob = avg_logprob_sum / seg_count
        avg_no_speech = no_speech_sum / seg_count
        # Higher logprob and lower no_speech_prob are better.
        return (avg_logprob * 2.0) - avg_no_speech + (len(text) * 0.001)

    return result_a if confidence(result_a) >= confidence(result_b) else result_b


def is_low_confidence_transcription(result) -> bool:
    segments = (result or {}).get("segments", []) or []
    if not segments:
        return True

    avg_logprob = sum(float(s.get("avg_logprob", -2.0)) for s in segments) / max(len(segments), 1)
    avg_no_speech = sum(float(s.get("no_speech_prob", 1.0)) for s in segments) / max(len(segments), 1)
    text = ((result or {}).get("text") or "").strip()

    return (avg_logprob < -1.0) or (avg_no_speech > 0.65) or (len(text) < 6)


def transcribe_with_retry(model, audio_path: str, options: dict):
    primary = model.transcribe(audio_path, **options)
    if not is_low_confidence_transcription(primary):
        return primary

    retry_options = dict(options)
    # Retry without prompt bias and with broader search when confidence is low.
    retry_options.pop("initial_prompt", None)
    retry_options["temperature"] = (0.0, 0.2, 0.4)
    retry_options["beam_size"] = max(int(retry_options.get("beam_size", 8)), 10)
    retry_options["best_of"] = max(int(retry_options.get("best_of", 8)), 10)
    retry_options["condition_on_previous_text"] = True

    retry = model.transcribe(audio_path, **retry_options)
    return pick_better_transcription(primary, retry)


def normalize_medical_terms(text: str) -> str:
    """
    Normalize commonly misheard medical terms to improve clinical readability.
    Extend via env MEDICAL_TERM_CORRECTIONS as:
    wrong1:correct1,wrong2:correct2
    """
    if not text:
        return text

    corrected = text

    # Built-in corrections for frequent ASR confusion in prescriptions.
    corrections = {
        r"\bpara\s*ceta?mol\b": "paracetamol",
        r"\bparacetamal\b": "paracetamol",
        r"\bparacitamol\b": "paracetamol",
        r"\bparasitamol\b": "paracetamol",
        r"\bparastamol\b": "paracetamol",
        r"\bazithromicin\b": "azithromycin",
        r"\bamoxycillin\b": "amoxicillin",
        r"\bamoxillin\b": "amoxicillin",
        r"\bdolo\s*650\b": "Dolo 650",
        r"\bpcm\b": "paracetamol",
    }

    # Optional custom corrections from env for your local terminology.
    custom = os.getenv("MEDICAL_TERM_CORRECTIONS", "").strip()
    if custom:
        for pair in custom.split(","):
            if ":" in pair:
                wrong, right = pair.split(":", 1)
                wrong = wrong.strip()
                right = right.strip()
                if wrong and right:
                    corrections[rf"\b{re.escape(wrong)}\b"] = right

    # Admin-configured dictionary terms from DB (misheard -> correct).
    for term in get_medical_terms():
        wrong = (term.get("wrong_term") or "").strip()
        right = (term.get("correct_term") or "").strip()
        if wrong and right:
            corrections[rf"\b{re.escape(wrong)}\b"] = right

    for wrong_pattern, right_term in corrections.items():
        corrected = re.sub(wrong_pattern, right_term, corrected, flags=re.IGNORECASE)

    # Fuzzy correction for near-miss medicine spellings in word-level output.
    # This only applies when a close match is very likely.
    right_terms = list({v for v in corrections.values() if v})
    parts = re.findall(r"[A-Za-z0-9]+|[^A-Za-z0-9]+", corrected)
    for i, p in enumerate(parts):
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{3,}", p):
            match = difflib.get_close_matches(p.lower(), [r.lower() for r in right_terms], n=1, cutoff=0.88)
            if match:
                best_lower = match[0]
                for rt in right_terms:
                    if rt.lower() == best_lower:
                        parts[i] = rt
                        break
    corrected = "".join(parts)

    return corrected


def normalize_clinical_sentences(text: str) -> str:
    """
    Light cleanup for common ASR sentence-level mistakes in advice statements.
    Keeps this conservative to avoid changing meaning.
    """
    if not text:
        return text

    cleaned = re.sub(r"\s+", " ", text).strip()

    sentence_corrections = {
        r"\badvice the patient\b": "advise the patient",
        r"\badvise patient\b": "advise the patient",
        r"\btake a rest\b": "take rest",
        r"\bfor three days only\b": "for 3 days",
        r"\btwice a day\b": "twice daily",
        r"\bonce a day\b": "once daily",
        r"\bafter foods\b": "after food",
        r"\bbefore foods\b": "before food",
    }

    for wrong_pattern, right_phrase in sentence_corrections.items():
        cleaned = re.sub(wrong_pattern, right_phrase, cleaned, flags=re.IGNORECASE)

    # Basic readability polish
    if cleaned and cleaned[-1] not in ".!?":
        cleaned += "."
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned


# -------------------- SPLASH + LOGIN --------------------
@app.route("/")
def splash():
    clinic = get_clinic_info()
    return render_template("splash.html", clinic=clinic)


@app.route("/login", methods=["GET", "POST"])
def login():
    clinic = get_clinic_info()
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        if username == APP_USERNAME and password == APP_PASSWORD:
            session["user_logged_in"] = True
            return redirect(url_for("main_app"))
        error = "Invalid username or password."
    return render_template("login.html", clinic=clinic, error=error)


@app.route("/logout")
def logout():
    session.pop("user_logged_in", None)
    return redirect(url_for("login"))


# -------------------- MAIN APP --------------------
@app.route("/app")
def main_app():
    if not session.get("user_logged_in"):
        return redirect(url_for("login"))
    clinic = get_clinic_info()
    return render_template("index.html", clinic=clinic)


# -------------------- HELPER --------------------
def extract_sections_from_summary(summary: str):
    symptoms = ""
    medicines = ""

    for line in summary.splitlines():
        stripped = line.strip().lower()

        if stripped.startswith("symptoms"):
            symptoms = line.split(":", 1)[1].strip() if ":" in line else ""
        elif stripped.startswith("medicines"):
            medicines = line.split(":", 1)[1].strip() if ":" in line else ""

    return symptoms, medicines


# -------------------- RECORD (TRANSCRIBE ONLY) --------------------
@app.route("/record", methods=["POST"])
def record():

    audio = request.files["audio"]

    patient_name = request.form.get("patient_name")
    age = request.form.get("age")
    weight = request.form.get("weight")
    gender = request.form.get("gender")
    doctor_name = request.form.get("doctor_name")

    # Save using the uploaded filename so we keep the real container/extension (often .webm)
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    original_name = audio.filename or f"recorded_{ts}.webm"
    audio_path = os.path.join(UPLOAD_FOLDER, f"{ts}_{original_name}")
    audio.save(audio_path)

    try:
        # Always convert to a real 16kHz mono WAV for Whisper (fast + reliable)
        wav_path = os.path.join(UPLOAD_FOLDER, f"{ts}_converted.wav")
        if not convert_audio(audio_path, wav_path):
            return jsonify({"error": "Audio conversion failed. Please try again."}), 500

        model = get_model()
        language = (request.form.get("language") or os.getenv("WHISPER_LANGUAGE", "")).strip().lower()
        transcribe_options = {
            "fp16": False,
            "condition_on_previous_text": False,
            "temperature": 0.0,
            "beam_size": int(os.getenv("WHISPER_BEAM_SIZE", "8")),
            "best_of": int(os.getenv("WHISPER_BEST_OF", "8")),
            # Filter no-speech segments to avoid prompt-like hallucinated output.
            "no_speech_threshold": float(os.getenv("WHISPER_NO_SPEECH_THRESHOLD", "0.6")),
            "logprob_threshold": float(os.getenv("WHISPER_LOGPROB_THRESHOLD", "-1.0")),
        }
        prompt = os.getenv("WHISPER_INITIAL_PROMPT", "").strip()
        if prompt:
            transcribe_options["initial_prompt"] = prompt
        if language and language != "auto":
            transcribe_options["language"] = language

        raw_result = transcribe_with_retry(model, wav_path, transcribe_options)

        # Try speech-focused enhancement for unclear/low-volume recordings.
        enhanced_result = {"text": ""}
        enhanced_wav_path = os.path.join(UPLOAD_FOLDER, f"{ts}_enhanced.wav")
        if enhance_audio_for_speech(wav_path, enhanced_wav_path):
            enhanced_result = transcribe_with_retry(model, enhanced_wav_path, transcribe_options)

        result = pick_better_transcription(raw_result, enhanced_result)
        text = result.get("text", "")
        if text:
            text = normalize_clinical_sentences(normalize_medical_terms(text.strip()))

        return jsonify({"text": text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------- GENERATE REPORT (FROM EDITED TEXT) --------------------
@app.route("/generate-report", methods=["POST"])
def generate_report():
    data = request.get_json() or {}

    patient_name = (data.get("patient_name") or "").strip()
    age = (data.get("age") or "").strip()
    weight = (data.get("weight") or "").strip()
    gender = (data.get("gender") or "").strip()
    doctor_name = (data.get("doctor_name") or "").strip()
    edited_text = (data.get("text") or "").strip()

    if not edited_text:
        return jsonify({"error": "No text provided to generate report."}), 400

    try:
        cleaned_text = clean_text(edited_text)
        summary = summarize_text(cleaned_text)

        pdf_path = create_pdf(summary, patient_name, age, gender, doctor_name)

        global latest_pdf
        latest_pdf = pdf_path

        symptoms, medicines = extract_sections_from_summary(summary)

        now = datetime.now()
        visit_date = now.strftime("%Y-%m-%d")
        visit_time = now.strftime("%H:%M:%S")

        visit_id = save_visit(
            patient_name=patient_name,
            age=age,
            weight=weight,
            gender=gender,
            contact_email="",
            visit_date=visit_date,
            visit_time=visit_time,
            doctor_name=doctor_name,
            department="",
            symptoms=symptoms,
            diagnosis="",
            medicines=medicines,
            advice="",
            full_prescription=summary,
            pdf_path=pdf_path,
            language_translated="en",
        )

        return jsonify({
            "summary": summary,
            "visit_id": visit_id,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------- TRANSLATE --------------------
@app.route("/translate", methods=["POST"])
def translate_summary():
    data = request.get_json() or {}

    summary = (data.get("summary") or "").strip()
    target_lang = (data.get("language") or "").strip()
    source_lang = (data.get("source_language") or "auto").strip()
    visit_id = data.get("visit_id")

    if not summary:
        return jsonify({"error": "No summary available for translation."}), 400
    if not target_lang:
        return jsonify({"error": "Please choose a target language."}), 400

    if source_lang == target_lang:
        return jsonify({"translated_summary": summary})

    try:
        translated_text = GoogleTranslator(source=source_lang, target=target_lang).translate(summary)

        if visit_id:
            update_visit_language(int(visit_id), target_lang)

        return jsonify({
            "translated_summary": translated_text
        })

    except Exception as e:
        # Fallback to source auto-detection if explicit source fails.
        try:
            translated_text = GoogleTranslator(source="auto", target=target_lang).translate(summary)
            if visit_id:
                update_visit_language(int(visit_id), target_lang)
            return jsonify({"translated_summary": translated_text})
        except Exception:
            return jsonify({"error": str(e)}), 500


# -------------------- DOWNLOAD --------------------
@app.route("/download")
def download():
    pdf_file = latest_pdf if latest_pdf and os.path.exists(latest_pdf) else None

    if not pdf_file:
        pdf_candidates = glob.glob('prescription_*.pdf')
        if pdf_candidates:
            pdf_file = max(pdf_candidates, key=os.path.getctime)

    if not pdf_file:
        return jsonify({"error": "PDF not found"}), 404

    response = make_response(send_file(pdf_file, as_attachment=True))
    response.headers["Cache-Control"] = "no-store"
    return response


# -------------------- EMAIL --------------------
@app.route("/send-email", methods=["POST"])
def send_email_route():
    data = request.get_json()

    recipient_email = data.get("email")
    summary_text = data.get("summary")
    visit_id = data.get("visit_id")

    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    try:
        msg = EmailMessage()
        msg["Subject"] = "Medical Prescription Report"
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg.set_content(summary_text)

        pdf_path = latest_pdf

        with open(pdf_path, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename="prescription.pdf")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)

        if visit_id:
            update_visit_contact_email(int(visit_id), recipient_email)

        return jsonify({"message": "Email Sent Successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------- ADMIN --------------------
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        # Simple hard-coded credentials; can be moved to environment later
        if username == "admin" and password == "admin123":
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Invalid username or password."

    clinic = get_clinic_info()
    return render_template("admin_login.html", error=error, clinic=clinic)


@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    stats = get_stats()
    visits = get_recent_visits()
    clinic = get_clinic_info()
    medical_terms = get_medical_terms()

    return render_template(
        "admin.html",
        stats=stats,
        visits=visits,
        clinic=clinic,
        medical_terms=medical_terms,
    )


@app.route("/admin/medical-terms/add", methods=["POST"])
def add_medical_term():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    wrong_term = (request.form.get("wrong_term") or "").strip()
    correct_term = (request.form.get("correct_term") or "").strip()
    upsert_medical_term(wrong_term, correct_term)
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/medical-terms/delete", methods=["POST"])
def remove_medical_term():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    term_id_raw = (request.form.get("term_id") or "").strip()
    if term_id_raw.isdigit():
        delete_medical_term(int(term_id_raw))
    return redirect(url_for("admin_dashboard"))


def can_manage_medical_terms() -> bool:
    return bool(session.get("user_logged_in") or session.get("admin_logged_in"))


@app.route("/medical-terms/list", methods=["GET"])
def list_medical_terms():
    if not can_manage_medical_terms():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"terms": get_medical_terms()})


@app.route("/medical-terms/add", methods=["POST"])
def add_medical_term_main():
    if not can_manage_medical_terms():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    wrong_term = (data.get("wrong_term") or "").strip()
    correct_term = (data.get("correct_term") or "").strip()
    ok = upsert_medical_term(wrong_term, correct_term)
    if not ok:
        return jsonify({"error": "Both terms are required."}), 400
    return jsonify({"message": "Saved"})


@app.route("/medical-terms/delete", methods=["POST"])
def remove_medical_term_main():
    if not can_manage_medical_terms():
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json() or {}
    term_id = data.get("term_id")
    try:
        delete_medical_term(int(term_id))
    except Exception:
        return jsonify({"error": "Invalid term id."}), 400
    return jsonify({"message": "Deleted"})


# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(debug=True)