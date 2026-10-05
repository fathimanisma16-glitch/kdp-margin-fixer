import streamlit as st
from pypdf import PdfReader, PdfWriter, PageObject, Transformation
from io import BytesIO

# Page configuration
st.set_page_config(
    page_title="KDP Interior Margin Fixer",
    page_icon="📖",
    layout="centered"
)

# KDP Gutter calculation based on Amazon standards
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

# App Header
st.title("📖 KDP Interior Preflight & Margin Fixer")
st.markdown("""
Automatically adjusts interior PDFs exported from **Canva, InDesign, or Word** to meet Amazon KDP's mandatory gutter and safe-zone specifications.
""")

# File Uploader
uploaded_file = st.file_uploader(
    "Upload your raw PDF interior",
    type=["pdf"],
    help="Upload your multi-page manuscript or printable journal interior."
)

if uploaded_file:
    # Read the PDF into memory
    input_bytes = BytesIO(uploaded_file.read())
    reader = PdfReader(input_bytes)
    total_pages = len(reader.pages)
    
    # Extract dimensions of first page
    first_page = reader.pages[0]
    page_w_pt = float(first_page.mediabox.width)
    page_h_pt = float(first_page.mediabox.height)
    
    page_w_in = page_w_pt / 72.0
    page_h_in = page_h_pt / 72.0
    
    gutter_in = get_kdp_gutter_inches(total_pages)
    gutter_pt = gutter_in * 72.0
    min_outside_pt = MIN_OUTSIDE_MARGIN_IN * 72.0

    st.divider()
    st.subheader("📊 Document Diagnostics")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Pages", f"{total_pages}")
    col2.metric("Detected Trim", f"{page_w_in:.2f}\" × {page_h_in:.2f}\"")
    col3.metric("Required Gutter", f"{gutter_in:.3f}\"")

    st.info(
        f"💡 **Binding Geometry Applied:** Odd pages (recto) will have a **{gutter_in:.3f}\"** left gutter. "
        f"Even pages (verso) will have a **{gutter_in:.3f}\"** right gutter."
    )

    # Process and Download
    if st.button("🚀 Fix Margins & Prepare KDP File", type="primary"):
        with st.spinner("Processing document layout..."):
            writer = PdfWriter()
            
            for idx, page in enumerate(reader.pages):
                page_num = idx + 1
                pw = float(page.mediabox.width)
                ph = float(page.mediabox.height)

                # Printable envelope calculation
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

            output_stream = BytesIO()
            writer.write(output_stream)
            output_bytes = output_stream.getvalue()

        st.success("✅ Margins adjusted and scaled to safe printable bounds!")
        
        # Download button
        st.download_button(
            label="📥 Download Print-Ready PDF",
            data=output_bytes,
            file_name=f"kdp_ready_{uploaded_file.name}",
            mime="application/pdf"
        )

# Footer
st.divider()
st.caption("Powered by Modern Desk Lab • Built with Python & Streamlit")
