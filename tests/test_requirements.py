"""Every third-party library the code imports must be listed in a requirements file (and pinned)."""
import ast, glob, os, re, sys, unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMPORT_TO_DIST = {"PyQt6": "pyqt6", "llama_cpp": "llama-cpp-python", "psutil": "psutil", "requests": "requests",
                  "watchdog": "watchdog", "pyttsx3": "pyttsx3", "certifi": "certifi"}


def listed(filename):
    out = {}
    for line in open(os.path.join(ROOT, filename), encoding="utf-8"):
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"([A-Za-z0-9_.\-]+)\s*((?:==|>=|<=|~=|<|>)[^;\s]*(?:\s*,\s*(?:==|>=|<=|<|>)[^;\s]*)*)?", line)
        out[m.group(1).lower().replace("_", "-")] = (m.group(2) or "").strip()
    return out


class T(unittest.TestCase):
    def test_all_imports_are_listed(self):
        local = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(ROOT, "src", "*.py"))}
        local |= {"sps_browser_app"}
        std = set(sys.stdlib_module_names)
        found = set()
        for f in glob.glob(os.path.join(ROOT, "src", "*.py")) + glob.glob(os.path.join(ROOT, "tools", "*.py")):
            for n in ast.walk(ast.parse(open(f, encoding="utf-8").read())):
                names = [a.name for a in n.names] if isinstance(n, ast.Import) else \
                        [n.module] if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module else []
                for m in names:
                    r = m.split(".")[0]
                    if r not in std and r not in local:
                        found.add(r)
        have = {}
        for fn in ("requirements-build.txt", "requirements-ai.txt", "requirements-optional.txt"):
            have.update(listed(fn))
        missing = sorted(r for r in found if IMPORT_TO_DIST.get(r, r.lower()) not in have)
        self.assertEqual(missing, [], "imported but not in any requirements file: %s" % missing)

    def test_core_libraries_are_pinned_exactly(self):
        b = listed("requirements-build.txt")
        for name in ("pyqt6", "pyqt6-webengine", "psutil", "watchdog", "requests", "certifi"):
            self.assertTrue(b[name].startswith("=="), name + " must be pinned with ==")

    def test_local_ai_pinned(self):
        a = listed("requirements-ai.txt")
        self.assertEqual(a["llama-cpp-python"], "==0.3.21")
        for name in ("numpy", "diskcache", "jinja2", "typing-extensions"):
            self.assertIn(name, a)
        txt = open(os.path.join(ROOT, "requirements-ai.txt"), encoding="utf-8").read()
        self.assertIn("abetlen.github.io/llama-cpp-python/whl/cpu", txt)


if __name__ == "__main__":
    unittest.main()
