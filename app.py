import streamlit as st
from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# Page Configuration
st.set_page_config(
    page_title="KDP Publisher Studio",
    page_icon="📚",
    layout="wide"
)

# =========================================================
# HELPER FUNCTIONS: INTERIOR LOGIC
# =========================================================
def get_kdp_gutter_inches(page_count: int) -> float:
    if page_count <= 150:
        return 0.375
    elif page_count <= 300:
        return 0.500
    elif page_count <= 500:
        return 0.625
    elif page_count <= 700:
        return 0.750
    else:
        return 0.875

MIN_OUTSIDE_MARGIN_IN = 0.25

# =========================================================
# HELPER FUNCTIONS: COVER TEMPLATE ENGINE
# =========================================================
PAPER_MULTIPLIERS = {
    "White Paper (B&W or Standard Color)": 0.002252,
    "Cream Paper (B&W)": 0.0025,
    "Premium Color Paper": 0.002347
}

TRIM_PRESETS = {
    '6.0" × 9.0" (Most Popular)': (6.0, 9.0),
    '8.5" × 11.0" (Notebooks & Workbooks)': (8.5, 11.0),
    '5.5" × 8.5" (Standard Digest)': (5.5, 8.5),
    '5.0" × 8.0" (Novels)': (5.0, 8.0),
    '7.0" × 10.0" (Activity Books)': (7.0, 10.0),
    '8.5" × 8.5" (Square / Children\'s)': (8.5, 8.5),
    'Custom Size': (0.0, 0.0)
}

def generate_cover_template_pdf(trim_w, trim_h, spine_w, total_w, total_h, page_count, paper_type):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(total_w * 72, total_h * 72))
    
    w_pt = total_w * 72
    h_pt = total_h * 72
    bleed_pt = 0.125 * 72
    spine_pt = spine_w * 72
    trim_w_pt = trim_w * 72
    trim_h_pt = trim_h * 72
    
    # 1. Background fill
    c.setFillColor(colors.HexColor("#FAFAFA"))
    c.rect(0, 0, w_pt, h_pt, fill=True, stroke=False)
    
    # 2. Bleed zones (0.125" cut strip)
    c.setFillColor(colors.HexColor("#FEE2E2"))
    c.rect(0, 0, w_pt, bleed_pt, fill=True, stroke=False)
    c.rect(0, h_pt - bleed_pt, w_pt, bleed_pt, fill=True, stroke=False)
    c.rect(0, 0, bleed_pt, h_pt, fill=True, stroke=False)
    c.rect(w_pt - bleed_pt, 0, bleed_pt, h_pt, fill=True, stroke=False)
    
    # 3. Spine zone
    spine_x1 = bleed_pt + trim_w_pt
    spine_x2 = spine_x1 + spine_pt
    c.setFillColor(colors.HexColor("#EFF6FF"))
    c.rect(spine_x1, bleed_pt, spine_pt, trim_h_pt, fill=True, stroke=False)
    
    # 4. Trim cut lines (outer dashed red)
    c.setStrokeColor(colors.HexColor("#EF4444"))
    c.setLineWidth(1)
    c.setDash(4, 4)
    c.rect(bleed_pt, bleed_pt, w_pt - (2 * bleed_pt), h_pt - (2 * bleed_pt), fill=False, stroke=True)
    
    # 5. Spine fold lines (blue)
    c.setStrokeColor(colors.HexColor("#3B82F6"))
    c.line(spine_x1, 0, spine_x1, h_pt)
    c.line(spine_x2, 0, spine_x2, h_pt)
    c.setDash()
    
    # 6. Safe zones (0.125" inside trim)
    safe_pt = 0.125 * 72
    c.setStrokeColor(colors.HexColor("#10B981"))
    c.setLineWidth(0.8)
    c.setDash(2, 2)
    # Back cover safe area
    c.rect(bleed_pt + safe_pt, bleed_pt + safe_pt, trim_w_pt - (2 * safe_pt), trim_h_pt - (2 * safe_pt), fill=False, stroke=True)
    # Front cover safe area
    c.rect(spine_x2 + safe_pt, bleed_pt + safe_pt, trim_w_pt - (2 * safe_pt), trim_h_pt - (2 * safe_pt), fill=False, stroke=True)
    c.setDash()
    
    # 7. Barcode Safe Box (Bottom right of back cover: 2.0" x 1.2")
    bc_w_pt = 2.0 * 72
    bc_h_pt = 1.2 * 72
    bc_x = spine_x1 - bc_w_pt - (0.25 * 72)
    bc_y = bleed_pt + (0.25 * 72)
    c.setFillColor(colors.HexColor("#FEE2E2"))
    c.setStrokeColor(colors.HexColor("#EF4444"))
    c.rect(bc_x, bc_y, bc_w_pt, bc_h_pt, fill=True, stroke=True)
    c.setFillColor(colors.HexColor("#991B1B"))
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(bc_x + bc_w_pt / 2, bc_y + bc_h_pt / 2 + 3, "BARCODE LOCATION")
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(bc_x + bc_w_pt / 2, bc_y + bc_h_pt / 2 - 7, "Keep clear of text & critical art")
    
    # 8. Visual Text Labels
    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString((bleed_pt + spine_x1) / 2, h_pt / 2 + 15, "BACK COVER")
    c.drawCentredString((spine_x2 + w_pt - bleed_pt) / 2, h_pt / 2 + 15, "FRONT COVER")
    
    if spine_pt >= 24:
        c.saveState()
        c.translate(spine_x1 + spine_pt / 2, h_pt / 2)
        c.rotate(270)
        c.drawCentredString(0, -3, f"SPINE ({spine_w:.3f}\")")
        c.restoreState()
        
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawCentredString((bleed_pt + spine_x1) / 2, h_pt / 2 - 6, f"Trim: {trim_w}\" × {trim_h}\"")
    c.drawCentredString((spine_x2 + w_pt - bleed_pt) / 2, h_pt / 2 - 6, f"Trim: {trim_w}\" × {trim_h}\"")
    
    # Header Banner
    c.setFillColor(colors.HexColor("#1E3A8A"))
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(bleed_pt + 10, h_pt - bleed_pt - 18, 
                 f"KDP COVER TEMPLATE • Canvas: {total_w:.3f}\" × {total_h:.3f}\" ({int(total_w * 300)} × {int(total_h * 300)} px @ 300 DPI) • {page_count} Pages • {paper_type}")
    
    c.save()
    return buf.getvalue()

# =========================================================
# APP INTERFACE
# =========================================================
st.title("📚 KDP Preflight Studio")
st.caption("All-in-one preflight utility for Amazon Kindle Direct Publishing print-on-demand books.")

tab_interior, tab_cover = st.tabs(["📖 Interior Margin Fixer", "🎨 Cover Calculator & Template Generator"])

# ---------------------------------------------------------
# TAB 1: INTERIOR MARGIN FIXER
# ---------------------------------------------------------
with tab_interior:
    st.subheader("Auto-Fix Interior Gutters & Safe Zones")
    st.markdown("Upload any raw multi-page PDF from **Canva, InDesign, or Word**. The engine recalculates alternating inside binding gutters and scales content safely.")
    
    uploaded_file = st.file_uploader("Drop raw interior PDF", type=["pdf"], key="interior_uploader")
    
    if uploaded_file:
        input_bytes = BytesIO(uploaded_file.read())
        reader = PdfReader(input_bytes)
        total_pages = len(reader.pages)
        
        first_page = reader.pages[0]
        pw_in = float(first_page.mediabox.width) / 72.0
        ph_in = float(first_page.mediabox.height) / 72.0
        
        gutter_in = get_kdp_gutter_inches(total_pages)
        gutter_pt = gutter_in * 72.0
        min_outside_pt = MIN_OUTSIDE_MARGIN_IN * 72.0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Page Count", f"{total_pages}")
        c2.metric("Detected Trim", f"{pw_in:.2f}\" × {ph_in:.2f}\"")
        c3.metric("Required Gutter", f"{gutter_in:.3f}\"")
        
        st.info(f"💡 **Alternating spine gutters applied:** Odd pages will have a **{gutter_in:.3f}\"** left gutter. Even pages will have a **{gutter_in:.3f}\"** right gutter.")
        
        if st.button("🚀 Fix Margins & Prepare Interior", type="primary"):
            with st.spinner("Processing document layout..."):
                writer = PdfWriter()
                for idx, page in enumerate(reader.pages):
                    page_num = idx + 1
                    pw = float(page.mediabox.width)
                    ph = float(page.mediabox.height)
                    
                    printable_w = pw - (gutter_pt + min_outside_pt)
                    printable_h = ph - (2 * min_outside_pt)
                    scale_factor = min(printable_w / pw, printable_h / ph, 0.96)
                    scaled_w = pw * scale_factor
                    scaled_h = ph * scale_factor
                    
                    is_odd = (page_num % 2 != 0)
                    tx = gutter_pt if is_odd else (pw - gutter_pt - scaled_w)
                    ty = (ph - scaled_h) / 2.0
                    
                    new_page = PageObject.create_blank_page(width=pw, height=ph)
                    transform = Transformation().scale(scale_factor, scale_factor).translate(tx=tx, ty=ty)
                    new_page.merge_transformed_page(page, transform)
                    writer.add_page(new_page)
                    
                out_stream = BytesIO()
                writer.write(out_stream)
                
            st.success("✅ Interior successfully converted to KDP specifications!")
            st.download_button(
                label="📥 Download Print-Ready Interior PDF",
                data=out_stream.getvalue(),
                file_name=f"kdp_ready_{uploaded_file.name}",
                mime="application/pdf"
            )

# ---------------------------------------------------------
# TAB 2: COVER CALCULATOR & TEMPLATE GENERATOR
# ---------------------------------------------------------
with tab_cover:
    st.subheader("Paperback Wrap Cover Calculator & Guide Generator")
    st.markdown("Calculate exact spine thickness, complete wrap dimensions, and download a custom guide template to design over in **Canva** or **Photoshop**.")
    
    col_left, col_right = st.columns([1, 1], gap="medium")
    
    with col_left:
        st.write("##### 1. Book Specifications")
        preset_choice = st.selectbox("Trim Size Preset", list(TRIM_PRESETS.keys()))
        
        if preset_choice == "Custom Size":
            c_w = st.number_input("Custom Width (inches)", min_value=4.0, max_value=12.0, value=6.0, step=0.1)
            c_h = st.number_input("Custom Height (inches)", min_value=4.0, max_value=16.0, value=9.0, step=0.1)
            trim_w, trim_h = c_w, c_h
        else:
            trim_w, trim_h = TRIM_PRESETS[preset_choice]
            
        page_count = st.number_input("Exact Interior Page Count", min_value=24, max_value=828, value=120, step=2)
        paper_type = st.selectbox("Paper & Interior Color", list(PAPER_MULTIPLIERS.keys()))
        
        # Calculations
        multiplier = PAPER_MULTIPLIERS[paper_type]
        spine_w = page_count * multiplier
        total_w = (2 * trim_w) + spine_w + 0.25   # 0.125" bleed on left + right = 0.25"
        total_h = trim_h + 0.25                  # 0.125" bleed on top + bottom = 0.25"
        
        # Pixels at 300 DPI (print standard)
        px_w = round(total_w * 300)
        px_h = round(total_h * 300)
        
    with col_right:
        st.write("##### 2. Exact Cover Dimensions")
        
        m1, m2 = st.columns(2)
        m1.metric("Spine Width", f"{spine_w:.3f}\" / {spine_w * 25.4:.1f} mm")
        m2.metric("Total Width", f"{total_w:.3f}\" / {total_w * 25.4:.1f} mm")
        
        m3, m4 = st.columns(2)
        m3.metric("Total Height", f"{total_h:.3f}\" / {total_h * 25.4:.1f} mm")
        m4.metric("Canva 300 DPI Size", f"{px_w} × {px_h} px")
        
        st.markdown(f"""
        > **Canva Custom Size Setup:**
        > * Create a new design with custom dimensions: **{total_w:.3f} × {total_h:.3f} inches** (or **{px_w} × {px_h} px**).
        """)
        
        # Generate Template Button
        template_bytes = generate_cover_template_pdf(
            trim_w=trim_w,
            trim_h=trim_h,
            spine_w=spine_w,
            total_w=total_w,
            total_h=total_h,
            page_count=page_count,
            paper_type=paper_type
        )
        
        st.download_button(
            label="🎨 Download Custom KDP Cover Guide (PDF)",
            data=template_bytes,
            file_name=f"kdp_cover_template_{trim_w}x{trim_h}_{page_count}p.pdf",
            mime="application/pdf",
            type="primary"
        )
        
    st.divider()
    st.write("##### 📖 How to Design Your Cover with This Template in Canva:")
    st.markdown("""
    1. Click **Download Custom KDP Cover Guide (PDF)** above.
    2. In **Canva**, click **Create a design** $\rightarrow$ **Custom size** $\rightarrow$ enter the exact dimensions shown in the metric card above.
    3. Upload the downloaded template PDF into Canva and drag it onto the canvas as the background layer (lock it).
    4. Design your front cover, spine text, and back cover over the guide. Keep all essential titles inside the **green dashed safe lines** and avoid placing art over the **red barcode box**.
    5. Delete or hide the guide template layer, then export as **PDF Print**!
    """)
