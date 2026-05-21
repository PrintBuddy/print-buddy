from fastapi import UploadFile
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
import shutil

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
        Decrypt an encrypted PDF and save the unencrypted version back to disk.
        This prevents CUPS from receiving encrypted bytes that would print as gibberish.
        """
        reader = PdfReader(path.as_posix())
        writer = PdfWriter()

        # Copy all pages from reader to writer
        # PyPDF2 automatically decrypts pages as they're read
        for page in reader.pages:
            writer.add_page(page)

        # Write the decrypted PDF back to the same path
        with open(path, "wb") as f:
            writer.write(f)
    
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
        

