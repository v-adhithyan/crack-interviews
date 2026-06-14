from pypdf import PdfReader


def extract_pdf_text(uploaded_file):
    current_position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else None

    try:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        reader = PdfReader(uploaded_file)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        return "\n\n".join(page_text for page_text in pages if page_text).strip()
    finally:
        if current_position is not None and hasattr(uploaded_file, "seek"):
            uploaded_file.seek(current_position)
