import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_install', ROOT / 'scripts/package_install.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class PackagingTests(unittest.TestCase):
    def test_existing_artifact_becomes_self_contained_and_wrong_pair_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            deps, plugin, output = (base / n for n in ('deps.tar.gz', 'plugin.zip', 'install.zip'))
            with tarfile.open(deps, 'w:gz') as tar:
                for name in ('py_modules/fugashi/__init__.py', 'py_modules/unidic_lite/__init__.py',
                             'py_modules/jamdict/__init__.py', 'py_modules/jamdict_data/__init__.py',
                             'python313/python/bin/python3.13'):
                    entry = tarfile.TarInfo(name)
                    entry.mode = 0o755
                    tar.addfile(entry, io.BytesIO())
            metadata = {'remote_binary': [{'name': 'plugin-dependencies.tar.gz',
                                          'sha256hash': hashlib.sha256(deps.read_bytes()).hexdigest()}]}
            with zipfile.ZipFile(plugin, 'w') as archive:
                archive.writestr('Old Name/dist/', '')
                for name in ('plugin.json', 'dist/index.js', 'py_modules/japanese_worker.py'):
                    archive.writestr('Old Name/' + name, '{}')
                archive.writestr('Old Name/main.py', 'BIN_RAPIDOCR_DIR = os.path.join(BIN_DIR, "rapidocr")')
                archive.writestr('Old Name/package.json', json.dumps(metadata))
            packager.package(plugin, deps, output)
            with zipfile.ZipFile(output) as archive:
                archive.extractall(base / 'unpacked')
                self.assertTrue((base / 'unpacked/decky-translator/dist').is_dir())
                self.assertNotIn('remote_binary', json.loads(archive.read('decky-translator/package.json')))
                self.assertEqual(archive.read('decky-translator/bin/plugin-dependencies.tar.gz'), deps.read_bytes())
                self.assertIn(b'BIN_PY_MODULES_DIR', archive.read('decky-translator/main.py'))
                self.assertTrue(all(n.startswith('decky-translator/') for n in archive.namelist()))
            with deps.open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                packager.package(plugin, deps, output)

    def test_extraction_marker_matches_actual_archive_layout(self):
        tree = ast.parse((ROOT / 'main.py').read_text())
        check = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_should_extract_dependencies')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            env = {'os': __import__('os')}
            for key, relative in [('DEPENDENCIES_ARCHIVE', 'plugin-dependencies.tar.gz'),
                                  ('EXTRACTION_MARKER', '.dependencies-extracted'),
                                  ('BIN_PY_MODULES_DIR', 'py_modules'),
                                  ('BIN_RAPIDOCR_DIR', 'py_modules/rapidocr'),
                                  ('BIN_PYTHON_DIR', 'python313')]:
                env[key] = str(base / relative)
            exec(compile(ast.Module(body=[check], type_ignores=[]), 'main.py', 'exec'), env)
            self.assertFalse(env['_should_extract_dependencies']())
            (base / 'plugin-dependencies.tar.gz').touch()
            self.assertTrue(env['_should_extract_dependencies']())
            (base / 'py_modules/rapidocr').mkdir(parents=True)
            (base / 'python313').mkdir()
            (base / '.dependencies-extracted').touch()
            self.assertFalse(env['_should_extract_dependencies']())
            (base / 'py_modules/rapidocr').rmdir()
            self.assertTrue(env['_should_extract_dependencies']())
