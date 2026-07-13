from pathlib import Path
from types import SimpleNamespace

from src.core.file_manager import FileManager


class TestGenerateFilePathTraversal:
    def test_parent_directory_traversal_is_stripped(self, tmp_path):
        fm = FileManager()
        upload_dir = tmp_path / "uploads"
        file = SimpleNamespace(filename="../../etc/cron.d/malicious", content_type="application/pdf")

        result = fm.generate_file_path(upload_dir, file)

        assert result.parent == upload_dir
        assert ".." not in result.parts

    def test_absolute_path_filename_is_confined(self, tmp_path):
        fm = FileManager()
        upload_dir = tmp_path / "uploads"
        file = SimpleNamespace(filename="/etc/passwd", content_type="application/pdf")

        result = fm.generate_file_path(upload_dir, file)

        assert result.parent == upload_dir
        assert result == upload_dir / "passwd"

    def test_normal_filename_is_unaffected(self, tmp_path):
        fm = FileManager()
        upload_dir = tmp_path / "uploads"
        file = SimpleNamespace(filename="document.pdf", content_type="application/pdf")

        result = fm.generate_file_path(upload_dir, file)

        assert result == upload_dir / "document.pdf"
