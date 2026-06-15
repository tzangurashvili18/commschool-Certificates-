import streamlit as st
import io, os, re, copy, zipfile, tempfile
import openpyxl
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from pdf2image import convert_from_bytes
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(
    page_title="Commschool · Certificate Generator",
    page_icon="🎓",
    layout="centered"
)

# ── Fonts ──────────────────────────────────────────────────────────────────────
FONT_PATHS = {
    "GeoReg":  "/usr/share/fonts/truetype/noto/NotoSansGeorgian-Regular.ttf",
    "GeoBold": "/usr/share/fonts/truetype/noto/NotoSansGeorgian-Bold.ttf",
    "LatReg":  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "LatBold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}

@st.cache_resource
def register_rl_fonts():
    pdfmetrics.registerFont(TTFont('LatinRegular', FONT_PATHS["LatReg"]))
    pdfmetrics.registerFont(TTFont('LatinBold',    FONT_PATHS["LatBold"]))

register_rl_fonts()

PAGE_W, PAGE_H = 595.276, 841.89
DPI   = 200
SCALE = DPI / 72.0
GREEN = (48, 177, 66)
BLACK = (0, 0, 0)
RIGHT = 541

NOOP_DATE = b'<00130016000F00110013000F00130011001300170001000E000100120013000F00110016000F0013001100130017>Tj'
ENG_ERASE = [
    b'<0026004A004B0047004800030028005A0047004500570056004B005800470003003200E4004500470054>Tj',
    b'<002C00550003005200540047005500470050005600470046000300560051>Tj',
    b'[<0048005100540003005500570045004500470055005500480057004E>0.5 <004E005B000300450051004F0052004E00470056004B00500049>]TJ',
    b'<0045005100570054005500470003005100480003>Tj',
    b'[( Guranda T)98 (ordia)]TJ',
    b'(Data Analytics)Tj',
    b'(the )Tj',
]

def pil_font(key, pt):
    return ImageFont.truetype(FONT_PATHS[key], int(pt * DPI / 72))

def pt_to_px(pt):
    return int(pt * SCALE)

def mixed_parts_pil(text, font_geo, font_lat):
    segs = re.split(r'(\([A-Za-z0-9 ]+\))', text)
    parts = []
    for seg in segs:
        if not seg: continue
        parts.append((seg, font_lat if all(c.isascii() for c in seg) else font_geo))
    return parts

def draw_ra_pil(draw, y, parts, right_px):
    total = sum(draw.textlength(t, font=f) for t, f in parts)
    x = right_px - total
    for text, font in parts:
        draw.text((x, y), text, fill=BLACK, font=font)
        x += draw.textlength(text, font=font)

def draw_ra_rl(c, y, parts):
    total = sum(c.stringWidth(t, f, s) for t, f, s in parts)
    x = RIGHT - total
    for text, font, size in parts:
        c.setFont(font, size); c.drawString(x, y, text)
        x += c.stringWidth(text, font, size)

def img_to_pdf_page(img):
    png_buf = io.BytesIO()
    img.save(png_buf, format='PNG')
    png_buf.seek(0)
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=(PAGE_W, PAGE_H))
    c.drawImage(ImageReader(png_buf), 0, 0, width=PAGE_W, height=PAGE_H)
    c.save(); pdf_buf.seek(0)
    return PdfReader(pdf_buf).pages[0]

def generate_certificate(name_eng, name_geo, course_eng, course_geo, date, template_bytes, is_crash_course=True):
    template_imgs = convert_from_bytes(template_bytes, dpi=DPI)
    writer = PdfWriter()

    # ── Page 1: Georgian ──────────────────────────────────────────────────────
    img  = template_imgs[0].copy()
    draw = ImageDraw.Draw(img)
    draw.rectangle([pt_to_px(120), pt_to_px(390), pt_to_px(548), pt_to_px(515)], fill=GREEN)
    draw.rectangle([pt_to_px(55),  pt_to_px(636), pt_to_px(235), pt_to_px(664)], fill=GREEN)

    f_geo_reg  = pil_font("GeoReg",  15)
    f_geo_bold = pil_font("GeoBold", 15)
    f_lat_reg  = pil_font("LatReg",  12)
    f_lat_bold = pil_font("LatBold", 15)
    right_px   = pt_to_px(RIGHT)
    LH         = pt_to_px(23)
    y1 = pt_to_px(400); y2 = y1+LH; y3 = y2+LH

    draw_ra_pil(draw, y1, [('გადაეცემა ', f_geo_reg), (name_geo, f_geo_bold)], right_px)

    if is_crash_course:
        cp = [('"', f_lat_bold)] + mixed_parts_pil(course_geo, f_geo_bold, f_lat_bold) + [('"', f_lat_bold)]
        draw_ra_pil(draw, y2, cp, right_px)
        draw_ra_pil(draw, y3, [('ქრეშ კურსის წარმატებით დასრულებისთვის', f_geo_reg)], right_px)
    else:
        cp = mixed_parts_pil(course_geo, f_geo_bold, f_lat_bold)
        draw_ra_pil(draw, y2, cp + [('პროგრამის', f_geo_reg)], right_px)
        draw_ra_pil(draw, y3, [('წარმატებით დასრულებისთვის', f_geo_reg)], right_px)

    draw.text((pt_to_px(57.9), pt_to_px(644)), date, fill=BLACK, font=f_lat_reg)
    writer.add_page(img_to_pdf_page(img))

    # ── Page 2: English ───────────────────────────────────────────────────────
    img2  = template_imgs[1].copy()
    draw2 = ImageDraw.Draw(img2)
    draw2.rectangle([pt_to_px(200), pt_to_px(395), pt_to_px(548), pt_to_px(510)], fill=GREEN)
    draw2.rectangle([pt_to_px(55),  pt_to_px(636), pt_to_px(235), pt_to_px(664)], fill=GREEN)

    f19r = pil_font("LatReg",  19)
    f19b = pil_font("LatBold", 19)
    f12r = pil_font("LatReg",  12)

    draw_ra_pil(draw2, pt_to_px(419)-int(19*DPI/72), [('Is presented to ', f19r), (name_eng, f19b)], right_px)
    draw_ra_pil(draw2, pt_to_px(441)-int(19*DPI/72), [('for successfully completing', f19r)], right_px)

    if is_crash_course:
        draw_ra_pil(draw2, pt_to_px(463)-int(19*DPI/72), [('the crash course', f19r)], right_px)
        draw_ra_pil(draw2, pt_to_px(485)-int(19*DPI/72), [('"', f19r), (course_eng, f19b), ('"', f19r)], right_px)
    else:
        draw_ra_pil(draw2, pt_to_px(463)-int(19*DPI/72), [('the course of ', f19r), (course_eng, f19b)], right_px)

    draw2.text((pt_to_px(58.4), pt_to_px(644)), date, fill=BLACK, font=f12r)
    writer.add_page(img_to_pdf_page(img2))

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

def parse_excel(file_bytes):
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
    ws = wb.active
    students = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        name_eng = str(row[0]).strip() if row[0] else ''
        if not name_eng or name_eng == 'None': continue
        students.append({
            'name_eng':   name_eng,
            'name_geo':   str(row[1]).strip() if row[1] else '',
            'course_eng': str(row[2]).strip() if row[2] else '',
            'course_geo': str(row[3]).strip() if row[3] else '',
            'date':       str(row[4]).strip() if row[4] else '',
        })
    return students

# ── UI ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.block-container { max-width: 640px; padding-top: 2rem; }

.comm-header {
    text-align: center;
    padding: 2rem 0 1.5rem;
}

.comm-logo {
    display: inline-grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
    margin-bottom: 1rem;
}

.comm-logo span {
    display: block;
    width: 18px; height: 18px;
    background: #30B143;
    border-radius: 3px;
}

h1 { font-size: 1.6rem !important; font-weight: 700 !important; margin-bottom: 0.25rem !important; }
.subtitle { color: #6B7280; font-size: 0.9rem; margin-bottom: 0; }

.stButton > button {
    width: 100%;
    background: #30B143 !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.65rem 1rem !important;
    transition: background 0.15s !important;
}

.stButton > button:hover {
    background: #1E8A30 !important;
}

.stDownloadButton > button {
    width: 100%;
    background: #111 !important;
    color: white !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.65rem 1rem !important;
}

.cert-success {
    background: #EBF7ED;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 0.85rem;
    color: #1E8A30;
    margin-bottom: 4px;
}

.cert-error {
    background: #FEF2F2;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 0.85rem;
    color: #B91C1C;
    margin-bottom: 4px;
}

.hint-box {
    background: #F9FAFB;
    border: 1px solid #E5E7EB;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    font-size: 0.82rem;
    color: #6B7280;
    margin-top: 1.5rem;
}

.hint-box strong { color: #111; }
</style>

<div class="comm-header">
  <div class="comm-logo">
    <span></span><span></span><span></span><span></span>
  </div>
  <h1>Certificate Generator</h1>
  <p class="subtitle">Commschool — generate personalized certificates in seconds</p>
</div>
""", unsafe_allow_html=True)

# ── File uploads ───────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("📄 Certificate Template (PDF)", type=["pdf"])
with col2:
    xlsx_file = st.file_uploader("📊 Student List (Excel)", type=["xlsx"])

# Course type
course_type = st.radio(
    "Course type",
    ["Crash course", "Regular course"],
    horizontal=True,
    help="Changes the wording on both pages"
)
is_crash = course_type == "Crash course"

st.divider()

# ── Generate ───────────────────────────────────────────────────────────────────
if st.button("✦ Generate Certificates", disabled=not (pdf_file and xlsx_file)):
    template_bytes = pdf_file.read()
    students = parse_excel(xlsx_file.read())

    if not students:
        st.error("No students found in the Excel file. Check your format.")
    else:
        st.write(f"**{len(students)} students found.** Generating certificates...")
        progress = st.progress(0)
        status   = st.empty()

        results = []
        errors  = []

        for i, s in enumerate(students):
            status.text(f"Generating {i+1}/{len(students)}: {s['name_eng']}...")
            try:
                cert_bytes = generate_certificate(
                    s['name_eng'], s['name_geo'],
                    s['course_eng'], s['course_geo'],
                    s['date'], template_bytes, is_crash
                )
                results.append((s['name_eng'], cert_bytes))
                st.markdown(f'<div class="cert-success">✅ {s["name_eng"]}</div>', unsafe_allow_html=True)
            except Exception as e:
                errors.append(s['name_eng'])
                st.markdown(f'<div class="cert-error">❌ {s["name_eng"]} — {str(e)[:60]}</div>', unsafe_allow_html=True)
            progress.progress((i + 1) / len(students))

        status.text(f"Done! {len(results)} certificates generated.")

        if results:
            # Build ZIP
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                for name, data in results:
                    zf.writestr(name.replace(' ', '_') + '.pdf', data)
            zip_buf.seek(0)

            st.divider()
            st.download_button(
                label=f"⬇ Download all {len(results)} certificates (ZIP)",
                data=zip_buf,
                file_name="commschool_certificates.zip",
                mime="application/zip"
            )

# ── Format hint ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hint-box">
  <strong>Excel format</strong> — row 1 is headers, one student per row<br><br>
  <strong>Column A:</strong> Student name in English &nbsp;·&nbsp;
  <strong>Column B:</strong> Student name in Georgian &nbsp;·&nbsp;
  <strong>Column C:</strong> Course (English) &nbsp;·&nbsp;
  <strong>Column D:</strong> Course (Georgian) &nbsp;·&nbsp;
  <strong>Column E:</strong> Date<br><br>
  <strong>Note:</strong> This tool is calibrated to the current Commschool certificate template.
  If the design changes, the template needs re-calibration.
</div>
""", unsafe_allow_html=True)
