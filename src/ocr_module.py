import pytesseract
import fitz  # PyMuPDF
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)

# Try to set Tesseract path, but don't fail if not found
try:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except Exception as e:
    logger.warning(f"Tesseract path not configured: {e}")

def extract_text_from_pdf(pdf_path: str, poppler_path=None) -> str:
    """
    Extract text from PDF using PyMuPDF with optional OCR via Tesseract.
    Falls back to basic text extraction if OCR fails.
    
    Args:
        pdf_path: Path to PDF file
        poppler_path: Unused (kept for backward compatibility)
    
    Returns:
        Extracted text from PDF
    """
    text = ""
    try:
        # First try direct text extraction from PDF
        pdf_document = fitz.open(pdf_path)
        
        for page_num in range(len(pdf_document)):
            try:
                page = pdf_document[page_num]
                # Try to extract text directly
                page_text = page.get_text()
                
                if page_text.strip():
                    # If we got text, use it
                    text += page_text
                else:
                    # If no text, try OCR on the page
                    try:
                        text += _ocr_page(page)
                    except Exception as e:
                        logger.warning(f"OCR failed for page {page_num + 1}: {e}")
            except Exception as e:
                logger.error(f"Error processing page {page_num + 1}: {e}")
                continue
        
        pdf_document.close()
        
    except Exception as e:
        logger.error(f"Error opening PDF: {e}")
        raise ValueError(f"Failed to process PDF: {str(e)}")
    
    if not text.strip():
        raise ValueError("No text could be extracted from the PDF")
    
    return text


def _ocr_page(page) -> str:
    """
    Perform OCR on a single PDF page using Tesseract.
    
    Args:
        page: PyMuPDF page object
    
    Returns:
        OCR extracted text
    """
    try:
        # Render page to image (300 DPI = 300/72 zoom)
        pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # OCR the image
        return pytesseract.image_to_string(img)
    except Exception as e:
        logger.warning(f"OCR extraction failed: {e}")
        # Fall back to basic text extraction
        try:
            return page.get_text()
        except Exception:
            return ""


def extract_text_from_pdf_batch(pdf_paths: list) -> dict:
    """
    Extract text from multiple PDF files.
    
    Args:
        pdf_paths: List of PDF file paths
    
    Returns:
        Dictionary with results and errors
    """
    results = {
        "successful": [],
        "failed": [],
        "total": len(pdf_paths)
    }
    
    for pdf_path in pdf_paths:
        try:
            text = extract_text_from_pdf(pdf_path)
            results["successful"].append({
                "file": pdf_path,
                "text": text,
                "status": "success"
            })
        except Exception as e:
            results["failed"].append({
                "file": pdf_path,
                "error": str(e),
                "status": "failed"
            })
    
    return results
