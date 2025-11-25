import streamlit as st
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO

# --- Page Configuration ---
st.set_page_config(page_title="Batch Number PDF Tool", page_icon="📄")


def get_text_positions(pdf_bytes):
    """
    Scans the PDF bytes for 'Batch Number:' and returns a dict of coordinates.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    positions = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Get page height for coordinate conversion later
        page_height = page.rect.height

        found = False
        pagedict = page.get_text("dict")

        for block in pagedict["blocks"]:
            for line in block.get("lines", []):
                words_concat = " ".join(span["text"] for span in line["spans"])

                if "Batch Number:" in words_concat:
                    for span in line["spans"]:
                        if "Batch Number:" in span["text"]:
                            # Calculate position
                            # x: end of the label + gap
                            # y: center of the text (PyMuPDF uses top-left as 0,0)
                            x_right = span["bbox"][2] + 10
                            y_center = (span["bbox"][1] + span["bbox"][3]) / 2 + 4

                            positions[page_num] = {
                                "x": x_right,
                                "y": y_center,
                                "page_height": page_height,
                                "found": True
                            }
                            found = True
                            break
                if found: break
            if found: break

    doc.close()
    return positions


def add_batch_number(input_file, batch_number, positions):
    """
    Overlays the batch number onto the PDF using the detected positions.
    """
    # Reset pointer to beginning of file since fitz read it already
    input_file.seek(0)

    reader = PdfReader(input_file)
    writer = PdfWriter()

    processed_count = 0

    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]

        # Check if we found the keyword on this page
        if page_num in positions:
            pos = positions[page_num]

            # Create the text overlay
            packet = BytesIO()
            # ReportLab canvas
            can = canvas.Canvas(packet, pagesize=A4)
            can.setFont("Times-Roman", 14)

            # Calculate Coordinates
            # ReportLab (0,0) is Bottom-Left. PyMuPDF (0,0) is Top-Left.
            # We must flip the Y axis based on the specific page height.
            x_point = pos["x"]
            y_point = pos["page_height"] - pos["y"]

            can.drawString(x_point, y_point, batch_number)
            can.save()

            # Merge
            packet.seek(0)
            overlay = PdfReader(packet)
            page.merge_page(overlay.pages[0])
            processed_count += 1

        writer.add_page(page)

    output_pdf = BytesIO()
    writer.write(output_pdf)
    output_pdf.seek(0)

    return output_pdf, processed_count


# --- UI Layout ---
st.title("Batch Number PDF Adder")
st.write(
    "Upload a PDF, enter a Batch Number, and the tool will insert it automatically wherever 'Batch Number:' is found.")

# 1. File Upload
uploaded_file = st.file_uploader("Select PDF File", type="pdf")

# 2. Input
batch_number = st.text_input("Enter Batch Number", placeholder="e.g., BN001234")

# 3. Process
if uploaded_file is not None and batch_number:
    if st.button("Process PDF"):
        with st.spinner("Scanning and processing PDF..."):
            try:
                # Read bytes from uploader
                bytes_data = uploaded_file.getvalue()

                # Find positions
                positions = get_text_positions(bytes_data)

                if not positions:
                    st.warning("Could not find the text 'Batch Number:' in this document.")
                else:
                    # Process PDF
                    output_pdf, count = add_batch_number(uploaded_file, batch_number, positions)

                    st.success(f"Success! Added batch number to {count} page(s).")

                    # Create new filename
                    original_name = uploaded_file.name.replace(".pdf", "")
                    new_filename = f"{original_name}_{batch_number}.pdf"

                    # Download Button
                    st.download_button(
                        label="Download Processed PDF",
                        data=output_pdf,
                        file_name=new_filename,
                        mime="application/pdf"
                    )

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
elif uploaded_file is not None and not batch_number:
    st.info("Please enter a Batch Number to proceed.")