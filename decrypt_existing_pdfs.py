#!/usr/bin/env python3
"""
Recovery script to decrypt all existing PDFs in the uploads directory.
Run this ONCE after deploying the new file_manager.py code.

Usage:
    cd backend
    source venv/bin/activate
    python3 decrypt_existing_pdfs.py
"""

import subprocess
import tempfile
import shutil
from pathlib import Path
from PyPDF2 import PdfReader

UPLOADS_PATH = Path("uploads")
PROCESSED = 0
FAILED = 0


def decrypt_with_ghostscript(pdf_path: Path) -> bool:
    """Try decrypting with Ghostscript (preferred)."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        
        subprocess.run([
            "gs",
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-dSAFER",
            "-sDEVICE=pdfwrite",
            "-dEncryptionR=0",
            f"-sOutputFile={tmp_path}",
            str(pdf_path)
        ], check=True, capture_output=True, timeout=30)
        
        shutil.move(tmp_path, str(pdf_path))
        return True
    except Exception as e:
        print(f"  ⚠ Ghostscript failed: {e}")
        return False


def decrypt_with_pypdf2(pdf_path: Path) -> bool:
    """Fallback to PyPDF2."""
    try:
        from PyPDF2 import PdfWriter
        
        reader = PdfReader(str(pdf_path))
        writer = PdfWriter()
        
        for page in reader.pages:
            writer.add_page(page)
        
        with open(pdf_path, "wb") as f:
            writer.write(f)
        
        return True
    except Exception as e:
        print(f"  ✗ PyPDF2 also failed: {e}")
        return False


def main():
    global PROCESSED, FAILED
    
    print(f"Scanning {UPLOADS_PATH} for PDFs...")
    
    pdfs = list(UPLOADS_PATH.rglob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs\n")
    
    for pdf_path in pdfs:
        try:
            reader = PdfReader(str(pdf_path))
            
            if reader.is_encrypted:
                print(f"🔒 Decrypting: {pdf_path.relative_to(UPLOADS_PATH)}")
                
                if decrypt_with_ghostscript(pdf_path):
                    print(f"  ✓ Decrypted with Ghostscript")
                    PROCESSED += 1
                elif decrypt_with_pypdf2(pdf_path):
                    print(f"  ✓ Decrypted with PyPDF2 fallback")
                    PROCESSED += 1
                else:
                    print(f"  ✗ Failed to decrypt")
                    FAILED += 1
            else:
                print(f"✓ Already unencrypted: {pdf_path.relative_to(UPLOADS_PATH)}")
        except Exception as e:
            print(f"✗ Error processing {pdf_path.name}: {e}")
            FAILED += 1
    
    print(f"\n{'='*60}")
    print(f"Summary: {PROCESSED} decrypted, {FAILED} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
