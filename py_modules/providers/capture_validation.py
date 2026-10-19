"""Validate screenshots with Pillow in its ABI-compatible portable runtime."""
import logging
import os
import subprocess

from .python_runtime import find_python

logger = logging.getLogger(__name__)


def valid_capture_png(plugin_dir, image_path):
    python = find_python(plugin_dir)
    if not python:
        logger.error('Cannot validate capture: compatible Python runtime unavailable')
        return False
    env = os.environ.copy()
    env.pop('PYTHONHOME', None)
    env.pop('LD_PRELOAD', None)
    env.pop('LD_LIBRARY_PATH', None)
    env['PYTHONPATH'] = os.pathsep.join((os.path.join(plugin_dir, 'bin', 'py_modules'),
                                      os.path.join(plugin_dir, 'py_modules')))
    try:
        result = subprocess.run(
            [python, '-B', '-c',
             'import sys; from PIL import Image; '
             'im=Image.open(sys.argv[1]); '
             'assert im.format == "PNG" and im.width > 0 and im.height > 0; '
             'im.load()', str(image_path)],
            env=env, capture_output=True, text=True, timeout=5,
        )
        if result.returncode:
            logger.warning('Invalid captured PNG: %s', result.stderr.strip()[-1000:])
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as error:
        logger.warning('Capture validation failed: %s', error)
        return False
