import os
import base64
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.utils import simpleSplit
from config import GUIDE_TEXTS

# ---- заглушка PNG 1x1
PNG_1PX = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMA"
    "AQAABQABDQottAAAAABJRU5ErkJggg=="
)

def ensure_file(path: str, b64: str):
    """Create file from base64 if it doesn't exist"""
    if not os.path.exists(path):
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))

def draw_pdf(path: str, title: str, body: str):
    """Generate PDF file with given title and body"""
    # Create directory if it doesn't exist (only if path contains directory)
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    margin = 2*cm
    y = h - margin
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    for line in simpleSplit(title, "Helvetica-Bold", 16, w - 2*margin):
        c.drawString(margin, y, line)
        y -= 22
    
    y -= 8
    
    # Body
    c.setFont("Helvetica", 12)
    lines = body.splitlines()
    for raw in lines:
        parts = simpleSplit(raw, "Helvetica", 12, w - 2*margin)
        for ln in parts:
            if y < margin + 20:
                c.showPage()
                y = h - margin
                c.setFont("Helvetica", 12)
            c.drawString(margin, y, ln)
            y -= 18
    
    c.showPage()
    c.save()

def ensure_pdfs():
    """Generate internal PDF guides if they don't exist"""
    from config import GUIDES
    
    # генерим только 4 внутренних PDF, внешний guide_7_blocks.pdf не трогаем
    for title, fname in GUIDES:
        if not os.path.exists(fname) and fname in GUIDE_TEXTS:
            draw_pdf(fname, title, GUIDE_TEXTS[fname])

def ensure_images():
    """Create placeholder images if they don't exist"""
    from config import WELCOME_PHOTO, DONATION_QR
    ensure_file(WELCOME_PHOTO, PNG_1PX)
    ensure_file(DONATION_QR, PNG_1PX)
