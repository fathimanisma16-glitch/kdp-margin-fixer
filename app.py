import streamlit as st
import textwrap
from io import BytesIO
from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

# Page Configuration
st.set_page_config(
    page_title="KDP Publisher Studio",
    page_icon="📚",
    layout="wide"
)

# =========================================================
# HELPER: INSTANT PDF RASTERIZER (PREVIEW ENGINE)
# =========================================================
def render_pdf_page_to_image(pdf_bytes, page_index=0, scale=1.5):
    """
    Renders a specific page of a PDF bytes object into a PIL Image for on-screen display.
    """
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_bytes)
        if 0 <= page_index < len(pdf):
            page = pdf[page_index]
            return page.render(scale=scale).to_pil()
    except Exception:
        return None
    return None

# =========================================================
# CONSTANTS & SPECIFICATIONS
# =========================================================
PAPER_MULTIPLIERS = {
    "White Paper (B&W or Standard Color)": 0.002252,
    "Cream Paper (B&W)": 0.0025,
    "Premium Color Paper": 0.002347
}

TRIM_PRESETS = {
    '6.0" × 9.0" (Standard Fiction / Non-Fiction)': (6.0, 9.0),
    '8.5" × 11.0" (Notebooks, Workbooks, Coloring)': (8.5, 11.0),
    '5.5" × 8.5" (Standard Digest)': (5.5, 8.5),
    '5.0" × 8.0" (Small Pocket Book)': (5.0, 8.0),
    '7.0" × 10.0" (Manuals & Activity Books)': (7.0, 10.0),
    '8.5" × 8.5" (Square Children\'s Book)': (8.5, 8.5),
    'Custom Size': (0.0, 0.0)
}

BLEED_IN = 0.125
MIN_OUTSIDE_MARGIN_IN = 0.25

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

# =========================================================
# ENGINE: 1-CLICK WRAP COVER ASSEMBLER
# =========================================================
def assemble_wrap_cover(front_img_bytes, trim_w, trim_h, spine_w, total_w, total_h, bg_hex, back_blurb="", spine_text=""):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(total_w * 72, total_h * 72))
    
    w_pt = total_w * 72
    h_pt = total_h * 72
    bleed_pt = BLEED_IN * 72
    trim_w_pt = trim_w * 72
    spine_pt = spine_w * 72
    
    spine_x1 = bleed_pt + trim_w_pt
    spine_x2 = spine_x1 + spine_pt
    
    # 1. Fill entire canvas (Back Cover + Spine) with the chosen theme color
    c.setFillColor(colors.HexColor(bg_hex))
    c.rect(0, 0, w_pt, h_pt, fill=True, stroke=False)
    
    # 2. Draw Front Cover Image (spans from spine right-edge to outer right bleed)
    front_area_w = trim_w_pt + bleed_pt
    front_reader = ImageReader(front_img_bytes)
    c.drawImage(front_reader, spine_x2, 0, width=front_area_w, height=h_pt)
    
    # 3. Barcode Safe Reservation Box on Back Cover (White rectangle for Amazon barcode scan)
    bc_w_pt = 2.0 * 72
    bc_h_pt = 1.2 * 72
    bc_x = spine_x1 - bc_w_pt - (0.25 * 72)
    bc_y = bleed_pt + (0.25 * 72)
    c.setFillColor(colors.white)
    c.rect(bc_x, bc_y, bc_w_pt, bc_h_pt, fill=True, stroke=False)
    
    # 4. Optional: Spine Text (centered vertically along the spine)
    if spine_text.strip() and spine_pt >= 24:
        c.saveState()
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 10)
        c.translate(spine_x1 + (spine_pt / 2), h_pt / 2)
        c.rotate(270)
        c.drawCentredString(0, -3.5, spine_text.strip())
        c.restoreState()
        
    # 5. Optional: Back Cover Blurb Text
    if back_blurb.strip():
        text_safe_x = bleed_pt + (0.4 * 72)
        text_safe_w = trim_w_pt - (0.8 * 72)
        top_y = h_pt - bleed_pt - (0.6 * 72)
        
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 10)
        
        lines = []
        for paragraph in back_blurb.split("\n"):
            if paragraph.strip():
                lines.extend(textwrap.wrap(paragraph, width=int(text_safe_w / 6.5)))
                lines.append("")  # paragraph spacing
            else:
                lines.append("")
                
        line_height = 14
        curr_y = top_y
        for line in lines:
            if curr_y > bc_y + bc_h_pt + 20: # Keep above barcode box
                c.drawString(text_safe_x, curr_y, line)
                curr_y -= line_height

    c.save()
    return buf.getvalue()

# =========================================================
# ENGINE: KDP REJECT DIMENSION RESIZER
# =========================================================
def fix_rejected_cover(cover_pdf_bytes, target_w_in, target_h_in):
    reader = PdfReader(cover_pdf_bytes)
    page = reader.pages[0]
    
    cur_w = float(page.mediabox.width)
    cur_h = float(page.mediabox.height)
    
    target_w_pt = target_w_in * 72.0
    target_h_pt = target_h_in * 72.0
    
    scale_x = target_w_pt / cur_w
    scale_y = target_h_pt / cur_h
    
    writer = PdfWriter()
    new_page = PageObject.create_blank_page(width=target_w_pt, height=target_h_pt)
    transform = Transformation().scale(scale_x, scale_y)
    new_page.merge_transformed_page(page, transform)
    writer.add_page(new_page)
    
    out_buf = BytesIO()
    writer.write(out_buf)
    return out_buf.getvalue(), cur_w / 72.0, cur_h / 72.0

# =========================================================
# APP INTERFACE
# =========================================================
st.title("📚 KDP Preflight Studio")
st.caption("All-in-one preflight and formatting utility for Amazon Kindle Direct Publishing print books.")

tab_interior, tab_cover = st.tabs(["📖 Interior Margin Fixer", "🎨 Cover Studio"])

# ---------------------------------------------------------
# TAB 1: INTERIOR MARGIN FIXER
# ---------------------------------------------------------
with tab_interior:
    st.subheader("Auto-Fix Interior Margins & Spine Gutters")
    st.markdown("Upload any raw multi-page PDF from **Canva, InDesign, or Word**. The engine recalculates alternating inside binding gutters and scales content safely.")
    
    uploaded_file = st.file_uploader("Drop raw interior PDF", type=["pdf"], key="interior_uploader")
    
    if uploaded_file:
        raw_pdf_bytes = uploaded_file.read()
        reader = PdfReader(BytesIO(raw_pdf_bytes))
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
                fixed_bytes = out_stream.getvalue()
                
            st.success("✅ Interior successfully converted to KDP specifications!")
            
            # --- LIVE INTERIOR PREVIEW SECTION ---
            st.write("#### 👁️ Visual Preflight Verification")
            st.caption("Verify how alternating gutters position the content away from the binding fold on opposite pages:")
            
            pv_col1, pv_col2 = st.columns(2)
            img_p1 = render_pdf_page_to_image(fixed_bytes, page_index=0, scale=1.3)
            img_p2 = render_pdf_page_to_image(fixed_bytes, page_index=1, scale=1.3) if total_pages > 1 else None
            
            with pv_col1:
                st.markdown("**Page 1 (Recto / Right Page)**")
                st.caption("⬅️ *Notice the wider gutter on the LEFT (Spine edge)*")
                if img_p1:
                    st.image(img_p1, use_container_width=True)
            
            with pv_col2:
                st.markdown("**Page 2 (Verso / Left Page)**")
                st.caption("➡️ *Notice the wider gutter on the RIGHT (Spine edge)*")
                if img_p2:
                    st.image(img_p2, use_container_width=True)
            
            st.divider()
            st.download_button(
                label="📥 Download Print-Ready Interior PDF",
                data=fixed_bytes,
                file_name=f"kdp_ready_{uploaded_file.name}",
                mime="application/pdf",
                type="primary"
            )

# ---------------------------------------------------------
# TAB 2: COVER STUDIO
# ---------------------------------------------------------
with tab_cover:
    st.subheader("Paperback Wrap Cover Studio")
    
    col_dim1, col_dim2, col_dim3 = st.columns([1.5, 1, 1.5])
    with col_dim1:
        preset_choice = st.selectbox("Trim Size", list(TRIM_PRESETS.keys()))
        if preset_choice == "Custom Size":
            trim_w = st.number_input("Width (in)", value=6.0, step=0.1)
            trim_h = st.number_input("Height (in)", value=9.0, step=0.1)
        else:
            trim_w, trim_h = TRIM_PRESETS[preset_choice]
            
    with col_dim2:
        page_count = st.number_input("Total Pages", min_value=24, max_value=828, value=120, step=2)
        
    with col_dim3:
        paper_type = st.selectbox("Paper Choice", list(PAPER_MULTIPLIERS.keys()))
        
    multiplier = PAPER_MULTIPLIERS[paper_type]
    spine_w = page_count * multiplier
    total_w = (2 * trim_w) + spine_w + (2 * BLEED_IN)
    total_h = trim_h + (2 * BLEED_IN)
    
    st.info(f"📐 **KDP Target Dimensions:** Total Canvas = **{total_w:.3f}\" × {total_h:.3f}\"** | Spine Width = **{spine_w:.3f}\"**")
    
    cover_mode = st.radio(
        "Choose Cover Mode:",
        ["✨ 1-Click Wrap Assembler (Upload Front Cover Only)", "🔧 KDP Reject Fixer (Resize Existing Wrap PDF)"],
        horizontal=True
    )
    
    st.divider()
    
    # MODE 1: 1-CLICK WRAP ASSEMBLER
    if "1-Click" in cover_mode:
        st.write("##### Assemble Full Panoramic Wrap from Front Cover")
        st.caption("Upload just your front cover artwork. The tool generates a matching back cover, spine, and barcode safe zone.")
        
        col_cov_left, col_cov_right = st.columns([1, 1], gap="medium")
        
        with col_cov_left:
            front_file = st.file_uploader("Upload Front Cover Image (PNG or JPG)", type=["png", "jpg", "jpeg"])
            bg_color = st.color_picker("Back Cover & Spine Color", value="#0F172A")
            spine_text = st.text_input("Spine Title (optional - recommended for 80+ pages)", placeholder="Book Title - Author Name")
            back_blurb = st.text_area("Back Cover Synopsis / Text (optional)", placeholder="Write a brief description or bullet points for the back cover...", height=130)
            
        with col_cov_right:
            if front_file:
                st.write("**Front Cover Input:**")
                st.image(front_file, width=200)
                
                if st.button("🚀 Generate Print-Ready Wrap PDF", type="primary"):
                    with st.spinner("Stitching cover wrap..."):
                        wrap_bytes = assemble_wrap_cover(
                            front_img_bytes=BytesIO(front_file.read()),
                            trim_w=trim_w,
                            trim_h=trim_h,
                            spine_w=spine_w,
                            total_w=total_w,
                            total_h=total_h,
                            bg_hex=bg_color,
                            back_blurb=back_blurb,
                            spine_text=spine_text
                        )
                    st.success("✅ Full panoramic wrap created and verified for KDP!")
                    
                    # --- LIVE COVER WRAP PREVIEW ---
                    st.write("#### 👁️ Panoramic Wrap Visual Preview")
                    st.caption(f"Dimensions: {total_w:.3f}\" × {total_h:.3f}\" (Back Cover | Spine | Front Cover)")
                    wrap_preview_img = render_pdf_page_to_image(wrap_bytes, page_index=0, scale=1.0)
                    if wrap_preview_img:
                        st.image(wrap_preview_img, use_container_width=True)
                    
                    st.download_button(
                        label="📥 Download KDP Wrap Cover (PDF)",
                        data=wrap_bytes,
                        file_name=f"kdp_cover_{trim_w}x{trim_h}_{page_count}p.pdf",
                        mime="application/pdf",
                        type="primary"
                    )
            else:
                st.info("👆 Upload your front cover image on the left to generate the complete wrap.")

    # MODE 2: REJECT FIXER
    else:
        st.write("##### Fix Rejected Full-Wrap PDF")
        st.caption("Amazon rejected your cover because the dimensions didn't match? Upload the PDF here to scale and conform it to KDP's exact measurements.")
        
        rejected_file = st.file_uploader("Upload Rejected Cover PDF", type=["pdf"], key="rejected_cov_uploader")
        
        if rejected_file:
            input_bytes = BytesIO(rejected_file.read())
            
            if st.button("🚀 Re-calculate & Conform Dimensions", type="primary"):
                with st.spinner("Resizing document to exact Amazon KDP bounds..."):
                    fixed_bytes, orig_w, orig_h = fix_rejected_cover(input_bytes, total_w, total_h)
                    
                st.success(f"✅ Converted from {orig_w:.2f}\" × {orig_h:.2f}\" ➔ **{total_w:.3f}\" × {total_h:.3f}\"** (Amazon Target)")
                
                # --- LIVE RESIZED COVER PREVIEW ---
                st.write("#### 👁️ Conformed Wrap Visual Preview")
                resized_preview_img = render_pdf_page_to_image(fixed_bytes, page_index=0, scale=1.0)
                if resized_preview_img:
                    st.image(resized_preview_img, use_container_width=True)
                
                st.download_button(
                    label="📥 Download Fixed Print-Ready Cover (PDF)",
                    data=fixed_bytes,
                    file_name=f"kdp_fixed_cover_{rejected_file.name}",
                    mime="application/pdf",
                    type="primary"
                )
