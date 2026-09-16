import os
from generate_pdf import create_pdf
from clean_text import clean_text

def test_clean_text():
    raw = "hello   hans world"
    expected = "hello humans world"
    cleaned = clean_text(raw)
    assert cleaned == expected, f"Expected '{expected}', got '{cleaned}'"
    print("clean_text passed")

def test_pdf_generation():
    if os.path.exists("seminar_report.pdf"):
        os.remove("seminar_report.pdf")
    if os.path.exists("AI_Seminar_Report.pdf"):
        os.remove("AI_Seminar_Report.pdf")
        
    create_pdf("Test report content.")
    
    if os.path.exists("seminar_report.pdf"):
        print("PDF generation passed: seminar_report.pdf created")
    else:
        print("PDF generation FAILED: seminar_report.pdf NOT created")
        if os.path.exists("AI_Seminar_Report.pdf"):
             print("Found AI_Seminar_Report.pdf instead - Fix failed")

if __name__ == "__main__":
    test_clean_text()
    test_pdf_generation()
