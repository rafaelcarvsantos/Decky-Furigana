"""Combine the inner plugin ZIP and dependency tarball; no third-party tools needed."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import zipfile


def package(plugin, dependencies, output):
    plugin, dependencies, output = map(Path, (plugin, dependencies, output))
    if output.resolve() in (plugin.resolve(), dependencies.resolve()):
        raise ValueError('Output must differ from inputs')
    with tarfile.open(dependencies, 'r:gz') as archive:
        members = {m.name.removeprefix('./'): m for m in archive.getmembers()}
        for name in ('py_modules/fugashi/__init__.py', 'py_modules/unidic_lite/__init__.py',
                     'py_modules/jamdict/__init__.py', 'py_modules/jamdict_data/__init__.py',
                     'python313/python/bin/python3.13'):
            if name not in members:
                raise ValueError(f'Dependency archive missing {name}')
        if not members['python313/python/bin/python3.13'].mode & 0o111:
            raise ValueError('Bundled Python is not executable')
        for member in members.values():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or path.parts[0] not in ('py_modules', 'python313'):
                raise ValueError(f'Unexpected dependency path: {member.name}')
    with zipfile.ZipFile(plugin) as source:
        manifests = [n for n in source.namelist() if n.endswith('/plugin.json') and n.count('/') == 1]
        if len(manifests) != 1:
            raise ValueError('Use the INNER plugin ZIP, with one top-level plugin directory')
        root = manifests[0].split('/')[0]
        metadata = json.loads(source.read(f'{root}/package.json'))
        # Old Actions artifacts have an accurate dependency hash even though their URL is wrong.
        for binary in metadata.get('remote_binary', []):
            if binary['name'] != 'plugin-dependencies.tar.gz':
                raise ValueError('Unexpected remote binary')
            with dependencies.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != binary['sha256hash']:
                raise ValueError('Dependency hash mismatch: use artifacts from the SAME workflow run')
        metadata.pop('remote_binary', None)
        for required in ('main.py', 'dist/index.js', 'py_modules/japanese_worker.py'):
            if f'{root}/{required}' not in source.namelist():
                raise ValueError(f'Plugin missing {required}')
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as target:
            for entry in source.infolist():
                path = PurePosixPath(entry.filename)
                if path.is_absolute() or '..' in path.parts or path.parts[0] != root:
                    raise ValueError(f'Unexpected plugin path: {entry.filename}')
                relative = '/'.join(path.parts[1:])
                if relative == 'bin' or relative.startswith('bin/'):
                    continue
                name = 'decky-translator/' + relative
                if entry.is_dir() and not name.endswith('/'):
                    name += '/'
                if relative == 'package.json':
                    data = (json.dumps(metadata, indent=2) + '\n').encode()
                elif relative == 'main.py':
                    # Also repair startup checks in existing pre-fix Actions artifacts.
                    data = source.read(entry).replace(
                        b'BIN_RAPIDOCR_DIR = os.path.join(BIN_DIR, "rapidocr")',
                        b'BIN_RAPIDOCR_DIR = os.path.join(BIN_PY_MODULES_DIR, "rapidocr")')
                else:
                    data = source.read(entry)
                target.writestr(name, data)
            # Already compressed; avoid spending CPU recompressing hundreds of MB.
            info = zipfile.ZipInfo('decky-translator/bin/plugin-dependencies.tar.gz')
            info.compress_type = zipfile.ZIP_STORED
            with target.open(info, 'w', force_zip64=True) as dest:
                with dependencies.open('rb') as stream:
                    shutil.copyfileobj(stream, dest)
    print(output.resolve())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plugin', help='Inner Decky Translator.zip, not Actions wrapper')
    parser.add_argument('dependencies', help='plugin-dependencies.tar.gz from the same build')
    parser.add_argument('output')
    args = parser.parse_args()
    package(args.plugin, args.dependencies, args.output)
