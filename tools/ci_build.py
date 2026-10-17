"""One build script for Windows, macOS and Linux (used by GitHub Actions, also works on your own PC):

    python tools/ci_build.py [--version 36.1.0]

 1. (optional) writes the version into src/SPS_BROWSER.py and installer/SPS_Browser_Setup.iss
 2. runs PyInstaller with SPS_Browser.spec  -> dist/SPS_Browser   (macOS: dist/SPS Browser.app)
 3. copies guide / licences / logo / support_form next to the program
 4. runs the program's own --selftest and stops with an error when a library is missing
"""
import argparse, glob, os, re, shutil, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
IS_WIN, IS_MAC = sys.platform == "win32", sys.platform == "darwin"


def step(msg):
    print("\n=== " + msg, flush=True)


def set_version(v):
    if not re.fullmatch(r"\d{1,4}\.\d{1,4}\.\d{1,4}", v):
        sys.exit("version must look like 36.1.0")
    for path, rx, rep in (("src/SPS_BROWSER.py", r'^(VERSION\s*=\s*")[^"]*(")', r"\g<1>%s\g<2>" % v),
                          ("installer/SPS_Browser_Setup.iss", r'^(#define APP_VERSION\s+")[^"]*(")', r"\g<1>%s\g<2>" % v)):
        text = open(path, encoding="utf-8").read()
        new, n = re.subn(rx, rep, text, count=1, flags=re.M)
        if n != 1:
            sys.exit("could not set the version in " + path)
        open(path, "w", encoding="utf-8", newline="").write(new)
    print("version set to", v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version")
    a = ap.parse_args()
    if a.version:
        step("Setting version")
        set_version(a.version)

    step("PyInstaller")
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "SPS_Browser.spec", "--noconfirm", "--clean"])

    dist = os.path.join(ROOT, "dist")
    if IS_MAC:
        app = os.path.join(dist, "SPS Browser.app")
        folder = os.path.join(app, "Contents", "MacOS")
        core = os.path.join(folder, "SPS_Browser_Core")
        main_exe = os.path.join(folder, "SPS_Browser")
    else:
        folder = os.path.join(dist, "SPS_Browser")
        core = os.path.join(folder, "SPS_Browser_Core" + (".exe" if IS_WIN else ""))
        main_exe = os.path.join(folder, "SPS_Browser" + (".exe" if IS_WIN else ""))
    for f in (main_exe, core):
        if not os.path.isfile(f):
            sys.exit("ERROR: missing after build: " + f)

    step("Copying guide, licences, logo")
    for f in ("SPS_BROWSER_GUIDE.md", "LICENSE.txt", "SPS_BROWSER_NOTICE.txt", "THIRD_PARTY_NOTICES.txt", "support_form.txt"):
        src = os.path.join(ROOT, "extras", f)
        if not os.path.isfile(src):
            sys.exit("ERROR: extras/%s is missing" % f)
        shutil.copy2(src, folder)
    os.makedirs(os.path.join(folder, "local_ai", "models"), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "extras", "local_ai", "models", "README_AI_MODELS.txt"), os.path.join(folder, "local_ai", "models"))
    os.makedirs(os.path.join(folder, "assets"), exist_ok=True)
    for f in glob.glob(os.path.join(ROOT, "assets", "sps_browser.*")):
        if f.endswith((".ico", ".png", ".icns")):
            shutil.copy2(f, os.path.join(folder, "assets"))

    step("Self-test of the built program")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox")
    rc = subprocess.call([core, "--selftest"], env=env, timeout=600)
    result = os.path.join(folder, "selftest_result.txt")
    text = open(result, encoding="utf-8").read() if os.path.isfile(result) else "(no result file)"
    print(text)
    if os.path.isfile(result):
        os.remove(result)
    if rc != 0 or "SELFTEST PASSED" not in text:
        if os.environ.get("SPS_SELFTEST_SOFT") == "1":      # best-effort systems (macOS): keep the build, but say so loudly
            print("::warning::SELF-TEST FAILED on this system - the package was still created but is NOT verified. Read the log above.")
        else:
            sys.exit("ERROR: the built program failed its self-test")
    for tmp in ("build", "_generated"):
        shutil.rmtree(os.path.join(ROOT, tmp), ignore_errors=True)
    print("\nBUILD OK ->", app if IS_MAC else folder)


if __name__ == "__main__":
    main()
