"""Serialized, bounded access to the optional offline reading worker."""
import json
import os
import select
import subprocess
import threading
from .python_runtime import find_python


class JapaneseService:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.process = None
        self.lock = threading.Lock()

    def request(self, action, **values):
        with self.lock:
            try:
                if self.process is None or self.process.poll() is not None:
                    python = find_python(self.plugin_dir)
                    if not python:
                        raise RuntimeError("Japanese reading requires the bundled Python 3.13 runtime.")
                    env = os.environ.copy()
                    paths = [os.path.join(self.plugin_dir, "bin", "py_modules"),
                             os.path.join(self.plugin_dir, "py_modules"), env.get("PYTHONPATH", "")]
                    env["PYTHONPATH"] = os.pathsep.join(paths)
                    env["PYTHONDONTWRITEBYTECODE"] = "1"
                    self.process = subprocess.Popen(
                        [python, "-u", os.path.join(self.plugin_dir, "py_modules", "japanese_worker.py")],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
                self.process.stdin.write((json.dumps(dict(values, action=action)) + "\n").encode())
                self.process.stdin.flush()
                if not select.select([self.process.stdout], [], [], 20)[0]:
                    raise TimeoutError("Japanese analysis timed out. Try a smaller dialogue region.")
                response = json.loads(self.process.stdout.readline())
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response["result"]
            except Exception:
                self._stop()
                raise

    def _stop(self):
        if self.process is not None:
            self.process.kill()
            self.process.communicate()
            self.process = None

    def close(self):
        with self.lock:
            self._stop()
