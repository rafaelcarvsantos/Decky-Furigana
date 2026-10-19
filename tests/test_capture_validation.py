from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'py_modules'))
from providers.capture_validation import valid_capture_png


class CaptureValidationTests(unittest.TestCase):
    def test_compressed_game_screen_and_truncated_png(self):
        from PIL import Image, ImageDraw
        import PIL
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.png'
            (Path(directory) / 'bin').mkdir()
            (Path(directory) / 'bin/py_modules').symlink_to(Path(PIL.__file__).resolve().parents[1], target_is_directory=True)
            image = Image.new('RGB', (1280, 800), 'black')
            ImageDraw.Draw(image).text((100, 100), 'Game menu', fill='white')
            image.save(path)
            self.assertLess(path.stat().st_size, 30000)
            with patch('providers.capture_validation.find_python', return_value=sys.executable):
                self.assertTrue(valid_capture_png(directory, path))
                path.write_bytes(path.read_bytes()[:100])
                self.assertFalse(valid_capture_png(directory, path))
                path.write_bytes(b'not a PNG')
                self.assertFalse(valid_capture_png(directory, path))

    def test_missing_runtime_is_reported_as_invalid(self):
        with patch('providers.capture_validation.find_python', return_value=None):
            self.assertFalse(valid_capture_png(str(ROOT), '/missing.png'))
