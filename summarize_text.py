import os
import re
import difflib
from typing import Optional, Dict
from openai import OpenAI
from dotenv import load_dotenv
from pediatric_database import PEDIATRIC_MEDICINE_LIST

# Load environment variables
load_dotenv()

# Create OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# =====================================================
# 🛡 MEDICINE CORRECTION LAYER
# =====================================================

def correct_medicine_names(text: str) -> str:
    """
    Auto-correct medicine names using built-in difflib.
    """

    words = text.split()
    corrected_words = []

    for word in words:
        clean_word = re.sub(r'[^a-zA-Z]', '', word).lower()

        if len(clean_word) < 4:
            corrected_words.append(word)
            continue

        match = difflib.get_close_matches(
            clean_word,
            PEDIATRIC_MEDICINE_LIST,
            n=1,
            cutoff=0.8
        )

        if match:
            corrected_words.append(match[0])
        else:
            corrected_words.append(word)

    return " ".join(corrected_words)


# =====================================================
# 🔎 SECTION EXTRACTOR
# =====================================================

def _extract_section(text: str, section: str) -> str:
    """
    Extract a section value from text like 'Symptoms: ...' using a regex parser.
    This is more robust than naive substring search (handles casing/spacing).
    """
    try:
        src = (text or "").strip()
        if not src:
            return ""

        pattern = rf"(?is)\b{re.escape(section)}\s*:\s*(.*?)(?=\n\s*(Symptoms|Medicines)\s*:|\Z)"
        m = re.search(pattern, src)
        return (m.group(1).strip() if m else "")
    except Exception:
        return ""


# =====================================================
# 🤖 GPT CALL (NEW API STYLE)
# =====================================================

def _call_llm_for_prescription(text: str) -> Optional[Dict[str, str]]:

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY missing")
        return None

    prompt = f"""
You are a medical prescription formatting assistant.

From the doctor's speech/notes below, extract and rewrite clearly into this EXACT 2-line format (no extra lines):

Symptoms: <only symptoms/complaints>
Medicines: <medicines with dose + frequency + duration, comma separated if multiple>

Rules (must follow):
- Output MUST be exactly these 2 lines, in this order, each on its own line.
- If a field is not mentioned, keep it blank after the colon.
- Do NOT merge multiple sections into one.
- Do NOT add any headings, bullet points, numbering, or explanations.
- Keep content short and clinical.

Doctor Notes:
{text}
"""

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0.2
        )

        content = response.output_text.strip()

        # Hard-normalize into the required 2-line format.
        # Even if the model adds extra whitespace, we recompose deterministically.
        s = _extract_section(content, "Symptoms")
        m = _extract_section(content, "Medicines")

        content = f"Symptoms: {s}\nMedicines: {m}"

        return {
            "symptoms": s,
            "medicines": m,
        }

    except Exception:
        import traceback
        traceback.print_exc()
        return None


# =====================================================
# 🧾 NORMALIZE OUTPUT
# =====================================================

def _normalize_prescription(fields: Optional[Dict[str, str]], fallback_source: str) -> str:

    base = {
        "symptoms": "",
        "medicines": "",
    }

    if fields:
        for key in base:
            if fields.get(key):
                base[key] = fields[key]

    # If LLM failed to split, try a small heuristic split; otherwise place everything into Symptoms.
    if (not fields) and fallback_source.strip():
        src = fallback_source.strip()
        lower = src.lower()

        def cut_after_any(prefixes):
            for p in prefixes:
                idx = lower.find(p)
                if idx != -1:
                    return idx
            return -1

        med_idx = cut_after_any([" medicine", " medicines", " tablet", " tab ", " syrup", " inj", " injection", " prescribe", " prescription", "mg", "ml"])
        # Pick earliest marker for each section if present
        markers = sorted([(i, "medicines") for i in [med_idx] if i != -1])

        if markers:
            first_i, first_key = markers[0]
            base["symptoms"] = src[:first_i].strip()
            rest = src[first_i:].strip()
            # Very simple: assign remaining to the first detected key
            base[first_key] = rest.strip()
        else:
            base["symptoms"] = src.replace("\n", " ")

    return (
        f"Symptoms: {base['symptoms']}\n"
        f"Medicines: {base['medicines']}"
    )


# =====================================================
# 🚀 MAIN FUNCTION
# =====================================================

def summarize_text(text: str) -> str:

    if not text or not text.strip():
        return "Symptoms: \nMedicines: "

    cleaned = text.strip()

    # Step 1: Correct medicine names BEFORE GPT
    corrected_text = correct_medicine_names(cleaned)

    # Step 2: Send corrected text to GPT
    llm_fields = _call_llm_for_prescription(corrected_text)

    # Step 3: Normalize output
    return _normalize_prescription(llm_fields, corrected_text)