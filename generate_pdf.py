from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import ImageReader
import os
import re


def create_pdf(summary, name, age, gender, doctor):

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    file_name = f"prescription_{timestamp}.pdf"
    c = canvas.Canvas(file_name, pagesize=letter)

    width, height = letter

    def ensure_space(y_pos: float, min_y: float = 80):
        """
        Start a new page if there isn't enough vertical space.
        Returns updated y position.
        """
        if y_pos < min_y:
            c.showPage()
            return height - 50
        return y_pos

    def wrap_words(text: str, max_width: float, font_name: str, font_size: int):
        """
        Wrap a string into lines that fit within max_width.
        """
        words = (text or "").split()
        if not words:
            return [""]

        lines = []
        current = words[0]
        for w in words[1:]:
            candidate = current + " " + w
            if stringWidth(candidate, font_name, font_size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = w
        lines.append(current)
        return lines

    def draw_labeled_wrapped(
        label: str,
        value: str,
        x: float,
        y_pos: float,
        max_width: float,
        font_name: str = "Helvetica",
        font_size: int = 11,
        line_gap: int = 16,
        label_gap: int = 6,
    ):
        """
        Draw 'Label: value' with proper wrapping.
        Subsequent wrapped lines are aligned under the value start.
        Returns updated y position.
        """
        c.setFont(font_name, font_size)

        label_text = (label or "").strip()
        value_text = (value or "").strip()

        if label_text:
            label_text = label_text if label_text.endswith(":") else (label_text + ":")

        label_w = stringWidth(label_text + " ", font_name, font_size) if label_text else 0
        value_x = x + label_w + label_gap if label_text else x
        avail = max_width - (value_x - x)
        avail = max(avail, 40)  # prevent zero/negative widths

        wrapped = wrap_words(value_text, avail, font_name, font_size) if value_text else [""]

        y_pos = ensure_space(y_pos)
        if label_text:
            c.drawString(x, y_pos, label_text)
            c.drawString(value_x, y_pos, wrapped[0])
        else:
            c.drawString(x, y_pos, wrapped[0])
        y_pos -= line_gap

        for extra in wrapped[1:]:
            y_pos = ensure_space(y_pos)
            c.drawString(value_x, y_pos, extra)
            y_pos -= line_gap

        return y_pos

    def parse_sections(text: str):
        """
        Robustly parse Symptoms/Medicines from a free-form text.
        Accepts variations in casing and whitespace.
        """
        src = (text or "").strip()
        if not src:
            return {"symptoms": "", "medicines": ""}

        def grab(section: str):
            pattern = rf"(?is)\b{re.escape(section)}\s*:\s*(.*?)(?=\n\s*(Symptoms|Medicines)\s*:|\Z)"
            m = re.search(pattern, src)
            return (m.group(1).strip() if m else "")

        return {
            "symptoms": grab("Symptoms"),
            "medicines": grab("Medicines"),
        }

    # Title
    # Clinic header banner (contains both logos as in your image)
    banner_path = os.path.join(os.path.dirname(__file__), "static", "clinic_header.png")
    if os.path.exists(banner_path):
        try:
            banner = ImageReader(banner_path)
            banner_h = 92
            c.drawImage(
                banner,
                0,
                height - banner_h,
                width=width,
                height=banner_h,
                preserveAspectRatio=True,
                anchor="n",
                mask="auto",
            )
        except Exception:
            pass

    c.setFont("Helvetica-Bold", 16)
    c.drawString(180, height - 120, "MEDICAL PRESCRIPTION")

    # Patient Details
    c.setFont("Helvetica", 12)

    y_position = height - 170

    c.drawString(50, y_position, f"Patient Name: {name}")
    y_position -= 20

    c.drawString(50, y_position, f"Age: {age}")
    y_position -= 20

    c.drawString(50, y_position, f"Gender: {gender}")
    y_position -= 20

    # Doctor name can be long; wrap it if needed
    y_position = draw_labeled_wrapped(
        "Doctor Name",
        str(doctor or ""),
        x=50,
        y_pos=y_position,
        max_width=width - 100,
        font_name="Helvetica",
        font_size=12,
        line_gap=18,
    )

    c.drawString(50, y_position, f"Date: {datetime.now().strftime('%d-%m-%Y')}")
    y_position -= 40

    # Prescription Heading
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y_position, "Doctor Notes / Prescription:")
    y_position -= 30

    # Structured Sections
    fields = parse_sections(summary)
    left_x = 50
    max_text_width = width - 100

    def draw_section(title: str, value: str, y_pos: float):
        y_pos = ensure_space(y_pos)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left_x, y_pos, f"{title}:")
        y_pos -= 18

        c.setFont("Helvetica", 11)
        val = (value or "").strip()
        if not val:
            c.drawString(left_x + 14, y_pos, "-")
            y_pos -= 16
            return y_pos

        for para in val.splitlines():
            p = para.strip()
            if not p:
                y_pos -= 6
                continue
            wrapped = wrap_words(p, max_text_width - 14, "Helvetica", 11)
            for wl in wrapped:
                y_pos = ensure_space(y_pos)
                c.drawString(left_x + 14, y_pos, wl)
                y_pos -= 16
        return y_pos

    y_position = draw_section("Symptoms", fields.get("symptoms"), y_position)
    y_position -= 6
    y_position = draw_section("Medicines", fields.get("medicines"), y_position)

    # Signature
    c.setFont("Helvetica", 12)
    c.drawString(width - 200, 100, "Doctor Signature")

    # Save PDF
    c.save()
    return file_name