import sqlite3
from datetime import datetime


DB_PATH = "speech.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    """
    Initialize the local SQLite database with:
    - a visits table that models a real hospital OPD visit log
    - a clinic_info table storing static clinic details
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            age INTEGER,
            gender TEXT,
            contact_email TEXT,
            visit_date TEXT,
            visit_time TEXT,
            doctor_name TEXT,
            department TEXT,
            symptoms TEXT,
            diagnosis TEXT,
            medicines TEXT,
            advice TEXT,
            full_prescription TEXT,
            pdf_path TEXT,
            language_translated TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Add weight column to visits table if it doesn't exist (for backwards compatibility)
    try:
        cursor.execute("ALTER TABLE visits ADD COLUMN weight TEXT")
    except sqlite3.OperationalError:
        # Column already exists
        pass

    # Create clinic_info table to store static clinic details
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS clinic_info (
            id INTEGER PRIMARY KEY,
            name TEXT,
            address TEXT,
            phone TEXT,
            email TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS medical_terms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wrong_term TEXT NOT NULL UNIQUE,
            correct_term TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Upsert a single row with the clinic details from the board image
    cursor.execute(
        """
        INSERT INTO clinic_info (id, name, address, phone, email)
        VALUES (1, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            address = excluded.address,
            phone = excluded.phone,
            email = excluded.email
        """,
        (
            "C.M. Health Clinic",
            "No. 111, Second Agraharam, Salem - 636 001.",
            "0427-4526126",
            "cmhcsalem2022@gmail.com",
        ),
    )

    conn.commit()
    conn.close()


def save_visit(
    patient_name: str,
    age: str,
    weight: str,
    gender: str,
    contact_email: str,
    visit_date: str,
    visit_time: str,
    doctor_name: str,
    department: str,
    symptoms: str,
    diagnosis: str,
    medicines: str,
    advice: str,
    full_prescription: str,
    pdf_path: str,
    language_translated: str = "en",
) -> int:
    """
    Insert a single visit row and return its auto-generated ID.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO visits (
            patient_name, age, weight, gender, contact_email,
            visit_date, visit_time, doctor_name, department,
            symptoms, diagnosis, medicines, advice,
            full_prescription, pdf_path, language_translated
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            patient_name,
            age,
            weight,
            gender,
            contact_email,
            visit_date,
            visit_time,
            doctor_name,
            department,
            symptoms,
            diagnosis,
            medicines,
            advice,
            full_prescription,
            pdf_path,
            language_translated,
        ),
    )

    visit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return visit_id


def update_visit_language(visit_id: int, language_code: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE visits SET language_translated = ? WHERE id = ?",
        (language_code, visit_id),
    )
    conn.commit()
    conn.close()


def update_visit_contact_email(visit_id: int, email: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE visits SET contact_email = ? WHERE id = ?",
        (email, visit_id),
    )
    conn.commit()
    conn.close()


def get_stats():
    """
    Compute high-level statistics for the admin dashboard:
    - total patients today
    - total visits this month
    - most common diagnosis
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Total visits today
    cursor.execute(
        """
        SELECT COUNT(*) FROM visits
        WHERE date(created_at) = date('now','localtime')
        """
    )
    total_visits_today = cursor.fetchone()[0] or 0

    # Total distinct patients today (by patient_name)
    cursor.execute(
        """
        SELECT COUNT(DISTINCT patient_name)
        FROM visits
        WHERE date(created_at) = date('now','localtime')
        """
    )
    total_patients_today = cursor.fetchone()[0] or 0

    # Total visits this month
    cursor.execute(
        """
        SELECT COUNT(*) FROM visits
        WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now','localtime')
        """
    )
    total_visits_this_month = cursor.fetchone()[0] or 0

    # Most common diagnosis
    cursor.execute(
        """
        SELECT diagnosis, COUNT(*) as cnt
        FROM visits
        WHERE diagnosis IS NOT NULL AND diagnosis <> ''
        GROUP BY diagnosis
        ORDER BY cnt DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    most_common_diagnosis = row[0] if row else None

    conn.close()

    return {
        "total_visits_today": total_visits_today,
        "total_patients_today": total_patients_today,
        "total_visits_this_month": total_visits_this_month,
        "most_common_diagnosis": most_common_diagnosis,
    }


def get_recent_visits(limit: int = 50):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            id,
            patient_name,
            age,
            weight,
            gender,
            contact_email,
            visit_date,
            visit_time,
            doctor_name,
            diagnosis,
            medicines,
            language_translated
        FROM visits
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()

    columns = [
        "id",
        "patient_name",
        "age",
        "weight",
        "gender",
        "contact_email",
        "visit_date",
        "visit_time",
        "doctor_name",
        "diagnosis",
        "medicines",
        "language_translated",
    ]
    return [dict(zip(columns, r)) for r in rows]


def get_clinic_info():
    """
    Retrieve the single clinic info row.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name, address, phone, email
        FROM clinic_info
        WHERE id = 1
        """
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "name": "",
            "address": "",
            "phone": "",
            "email": "",
        }

    return {
        "name": row[0],
        "address": row[1],
        "phone": row[2],
        "email": row[3],
    }


def get_medical_terms():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, wrong_term, correct_term
        FROM medical_terms
        ORDER BY wrong_term COLLATE NOCASE ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "wrong_term": r[1],
            "correct_term": r[2],
        }
        for r in rows
    ]


def upsert_medical_term(wrong_term: str, correct_term: str):
    wrong = (wrong_term or "").strip().lower()
    right = (correct_term or "").strip()
    if not wrong or not right:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO medical_terms (wrong_term, correct_term)
        VALUES (?, ?)
        ON CONFLICT(wrong_term) DO UPDATE SET
            correct_term = excluded.correct_term
        """,
        (wrong, right),
    )
    conn.commit()
    conn.close()
    return True


def delete_medical_term(term_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM medical_terms WHERE id = ?", (term_id,))
    conn.commit()
    conn.close()