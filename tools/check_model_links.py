"""
Checks that every model in the SPS Browser download list REALLY exists on Hugging Face and can be
downloaded WITHOUT an account. It downloads only the first 4 bytes of each file (instant, no big downloads).

Run:  python tools/check_model_links.py        (or double-click CHECK_MODEL_LINKS.bat)
"""
import sys, re, urllib.parse
try:
    import requests
except ImportError:
    sys.exit("Please run:  python -m pip install requests")

MODELS = [
    ("TinyLlama 1.1B",     "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF",        "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"),
    ("Qwen2 1.5B",         "Qwen/Qwen2-1.5B-Instruct-GGUF",                 "qwen2-1_5b-instruct-q4_k_m.gguf"),
    ("Phi-3 Mini 3.8B",    "bartowski/Phi-3-mini-4k-instruct-GGUF",         "Phi-3-mini-4k-instruct-Q4_K_M.gguf"),
    ("Qwen2.5-Coder 3B",   "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",           "qwen2.5-coder-3b-instruct-q8_0.gguf"),
    ("DeepSeek-R1 1.5B",   "bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF",  "DeepSeek-R1-Distill-Qwen-1.5B-Q8_0.gguf"),
    ("Gemma 2 2B",       "bartowski/gemma-2-2b-it-GGUF",                 "gemma-2-2b-it-Q4_K_M.gguf"),
]

def check(repo, fn):
    url = "https://huggingface.co/%s/resolve/main/%s" % (repo, urllib.parse.quote(fn))
    cur = url
    for _ in range(8):
        r = requests.get(cur, headers={"Range": "bytes=0-3", "User-Agent": "SPS-Browser-linkcheck"},
                         allow_redirects=False, stream=True, timeout=30)
        if r.status_code in (301, 302, 303, 307, 308):
            cur = urllib.parse.urljoin(cur, r.headers["Location"]); r.close(); continue
        break
    if r.status_code in (401, 403):
        return "NEEDS LOGIN (HTTP %d)" % r.status_code
    if r.status_code not in (200, 206):
        return "FAILED (HTTP %d)" % r.status_code
    head = r.raw.read(4, decode_content=False); r.close()
    m = re.search(r"/(\d+)$", r.headers.get("Content-Range", ""))
    size = int(m.group(1)) if m else int(r.headers.get("Content-Length", 0) or 0)
    ok = head == b"GGUF"
    return ("OK   %.2f GB, valid GGUF file" % (size / 1024**3)) if ok else "FAILED (not a GGUF file)"

print("Checking the download list (no account, no token)...\n")
bad = 0
for name, repo, fn in MODELS:
    try:
        res = check(repo, fn)
    except Exception as e:
        res = "FAILED (%s)" % e
    print("%-42s %s" % (name, res))
    if res.startswith("FAILED"):
        bad += 1
print("\n" + ("All downloadable models are reachable." if not bad else "%d model(s) failed - send me this screen." % bad))
