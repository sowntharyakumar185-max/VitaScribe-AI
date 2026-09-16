import re
from rapidfuzz import process
from medical_database import MEDICINE_LIST


def correct_medicine_names(text: str) -> str:
    """
    Detect possible medicine words and auto-correct them
    using fuzzy matching against MEDICINE_LIST.
    """

    words = text.split()
    corrected_words = []

    for word in words:
        clean_word = re.sub(r'[^a-zA-Z]', '', word).lower()

        # Skip very small words
        if len(clean_word) < 4:
            corrected_words.append(word)
            continue

        match, score, _ = process.extractOne(
            clean_word,
            MEDICINE_LIST
        )

        # High confidence auto-correct
        if score > 88:
            corrected_words.append(match)
        else:
            corrected_words.append(word)

    return " ".join(corrected_words)