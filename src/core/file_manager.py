from fastapi import UploadFile
from pathlib import Path
from PyPDF2 import PdfReader
import shutil
import subprocess
import tempfile

from .utils import generate_time
from .config import settings
from .logger import logger


class FileManager:
    def __init__(self):
        self.max_sz = settings.MAX_FILE_SIZE_MB * 1024 * 1024

        self.extensions = {
            "application/pdf" : "pdf",
            "image/png": "png",
            "image/jpeg": "jpeg"
        }

    def is_valid_format(self, file: UploadFile) -> bool:
        file_type = file.content_type
        return file_type in self.extensions.keys()
    
    def generate_file_path(self, dirpath: Path, file: UploadFile):
        dirpath.mkdir(parents=True, exist_ok=True)

        if file.filename is None:
            ext = self.extensions[file.content_type]  # type: ignore
            file.filename = f"file_{generate_time().strftime('%Y%m%d_%H%M%S')}.{ext}"
        else:
            # Strip any directory components the client-supplied filename
            # might carry (e.g. "../../etc/x") before it's ever joined
            # onto a real path.
            file.filename = Path(file.filename).name

        path = dirpath / file.filename

        counter = 1
        new_path = path
        while new_path.exists():
            file.filename = f"{path.stem}_({counter}){path.suffix}"
            new_path = path.with_stem(f"{path.stem}_({counter})")
            counter += 1

        return new_path

    def save_file(self, path: Path, file: UploadFile) -> int:
        """
        Receives a ``path`` object and a ``file`` object and saves it
        to the corresponding directory. Returns the size of file 
        in bytes. -1 is returned if file exceeds max size.
        """

        total_bytes = 0
        with open(path, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > self.max_sz:
                    buffer.close()
                    path.unlink(missing_ok=True)

                    return -1
                buffer.write(chunk)

        # If it's a PDF, decrypt it so CUPS can print it correctly
        if path.suffix.lower() == ".pdf":
            try:
                self._decrypt_pdf(path)
            except Exception as e:
                logger.warning(f"Failed to decrypt PDF {path.name}: {e}")
                # File is still saved even if decryption fails

        return total_bytes
    
    def _decrypt_pdf(self, path: Path) -> None:
        """
        Decrypt an encrypted PDF using Ghostscript and save the unencrypted version.
        Ghostscript is more robust than PyPDF2 for PDF processing and produces CUPS-compatible output.
        """
        try:
            # Use Ghostscript to convert PDF, which automatically decrypts it
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name
            
            # Run ghostscript to decrypt
            subprocess.run([
                "gs",
                "-q",
                "-dNOPAUSE",
                "-dBATCH",
                "-dSAFER",
                "-sDEVICE=pdfwrite",
                "-dEncryptionR=0",
                f"-sOutputFile={tmp_path}",
                str(path)
            ], check=True, capture_output=True, timeout=30)
            
            # Replace original with decrypted version
            shutil.move(tmp_path, str(path))
        except subprocess.CalledProcessError as e:
            # If ghostscript fails, try fallback with PyPDF2
            self._decrypt_pdf_fallback(path)
        except Exception as e:
            logger.warning(f"Ghostscript decryption failed for {path.name}, trying fallback: {e}")
            self._decrypt_pdf_fallback(path)
    
    def _decrypt_pdf_fallback(self, path: Path) -> None:
        """
        Fallback PDF decryption using PyPDF2 if Ghostscript fails.
        """
        from PyPDF2 import PdfWriter
        
        try:
            reader = PdfReader(path.as_posix())
            writer = PdfWriter()
            
            for page in reader.pages:
                writer.add_page(page)
            
            with open(path, "wb") as f:
                writer.write(f)
        except Exception as e:
            logger.error(f"Both decryption methods failed for {path.name}: {e}")
    
    def get_total_pages(self, path: Path) -> int:
        ext = path.suffix.lower()
        if ext == ".pdf":
            return len(PdfReader(path.as_posix()).pages)
        return 1
    
    def delete_file(self, path: Path) -> bool:
        if not path.exists():
            return False
        
        try:
            path.unlink(missing_ok=True)
            return True
        except Exception as e:
            return False
        
    def delete_directory(self, path: Path) -> bool:
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
            return True
        return False
        

