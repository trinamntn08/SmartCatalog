import fitz  # PyMuPDF

def load_catalog_pdf_text(filepath):
    """
    Load all text from a PDF catalog using PyMuPDF (fitz).
    Returns a full string with content from all pages.
    """
    try:
        doc = fitz.open(filepath)
        text = ""
        for page in doc:
            text += page.get_text() + "\n\n"
        return text
    except Exception as e:
        raise RuntimeError(f"Failed to load PDF: {str(e)}")
