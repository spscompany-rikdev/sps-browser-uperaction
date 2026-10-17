"""Install the local-AI library with graceful fallbacks. NEVER fails the build (the browser works without local AI).

    python tools/install_ai.py

 1. exact pinned version from requirements-ai.txt (llama-cpp-python 0.3.21, ready-made CPU wheel)
 2. if there is no wheel for this system: the newest ready-made CPU wheel that exists
 3. otherwise: no local AI (the build continues and says so)
"""
import os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INDEX = "https://abetlen.github.io/llama-cpp-python/whl/cpu"


def pip(*args):
    """--no-cache-dir: a damaged cached download (zlib errors) must never be reused. One automatic retry."""
    for _ in range(2):
        if subprocess.call([sys.executable, "-m", "pip", "install", "--no-cache-dir", *args], cwd=ROOT) == 0:
            return True
    return False


def installed_version():
    r = subprocess.run([sys.executable, "-c", "import llama_cpp; print(llama_cpp.__version__)"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def main():
    how = ""
    if pip("-r", "requirements-ai.txt"):
        how = "pinned version from requirements-ai.txt"
    elif pip("llama-cpp-python", "--only-binary=:all:", "--extra-index-url", INDEX, "numpy", "diskcache", "Jinja2", "typing-extensions"):
        how = "newest ready-made wheel (the pinned version has no wheel for this system)"
    v = installed_version()
    msg = ("llama-cpp-python %s installed (%s)" % (v, how)) if v else \
          "llama-cpp-python NOT available for this system - building WITHOUT local AI (everything else works)"
    print("\n[install_ai]", msg)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("- Local AI: %s\n" % msg)


if __name__ == "__main__":
    main()
