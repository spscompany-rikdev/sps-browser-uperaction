"""SPS Safety Check - logic only (no Qt), so it can be tested.

* Leaked passwords: the k-anonymity method of "Have I Been Pwned". Only the FIRST 5 characters of the password's SHA-1 are sent;
  the server answers with every hash suffix that starts like that and the match is made on this computer. The password never leaves.
* Reused / weak passwords: compared in memory only.
* Extensions / user scripts: a *heuristic* look at their code (not a virus verdict).
* Version: the signed update announcement (same check as the updater).
* Protection settings of the browser.
"""
import hashlib, re, urllib.request

HIBP_RANGE = "https://api.pwnedpasswords.com/range/"
OK, WARN, BAD, INFO = "ok", "warn", "bad", "info"

COMMON = {"password", "123456", "12345678", "123456789", "qwerty", "abc123", "111111", "letmein", "iloveyou", "admin", "welcome",
          "password1", "123123", "000000", "qwerty123", "1q2w3e4r", "dragon", "monkey", "football", "sunshine"}


def sha1_parts(password):
    h = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    return h[:5], h[5:]


def default_fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "SPS-Browser-SafetyCheck", "Add-Padding": "true"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def pwned_count(password, fetch=default_fetch, cache=None):
    """How many times the password appears in known leaks (0 = not found). Raises on network errors."""
    prefix, suffix = sha1_parts(password)
    if cache is not None and prefix in cache:
        body = cache[prefix]
    else:
        body = fetch(HIBP_RANGE + prefix)
        if cache is not None:
            cache[prefix] = body
    for line in body.splitlines():
        h, _, n = line.strip().partition(":")
        if h.upper() == suffix:
            try:
                return int(n)
            except ValueError:
                return 1
    return 0


def weak_reason(pw):
    if not pw:
        return "empty"
    if pw.lower() in COMMON:
        return "one of the most common passwords"
    if len(pw) < 8:
        return "shorter than 8 characters"
    if len(set(pw)) <= 3:
        return "almost only repeated characters"
    if pw.isdigit() or pw.isalpha():
        return "only digits or only letters"
    return None


def check_passwords(entries, fetch=default_fetch):
    """entries: [{'site','username','password'}]. Returns (results, network_ok)."""
    res, cache, net_ok = [], {}, True
    entries = [e for e in entries if e.get("password")]
    if not entries:
        return [(INFO, "Saved passwords", "No saved passwords to check.")], True
    by_pw = {}
    for e in entries:
        by_pw.setdefault(e["password"], []).append(e)
    leaked = weak = reused = 0
    for pw, group in by_pw.items():
        names = ", ".join(sorted({(g.get("site") or "?") for g in group}))[:90]
        if len(group) > 1:
            reused += len(group)
            res.append((WARN, "Reused password", "The same password is used for: %s" % names))
        wr = weak_reason(pw)
        if wr:
            weak += len(group)
            res.append((WARN, "Weak password", "%s - %s" % (names, wr)))
        if net_ok:
            try:
                n = pwned_count(pw, fetch, cache)
                if n:
                    leaked += len(group)
                    res.append((BAD, "Password found in a data leak", "%s - seen %s times in known leaks. Change it." % (names, n)))
            except Exception as ex:
                net_ok = False
                res.append((INFO, "Leak check skipped", "No connection to the check service (%s). Nothing was sent." % type(ex).__name__))
    if not (leaked or weak or reused) and net_ok:
        res.append((OK, "Saved passwords", "%d password(s) checked: none leaked, reused or weak." % len(entries)))
    return res, net_ok


RISK_RULES = [
    (r"\beval\s*\(|new\s+Function\s*\(", 2, "runs code built at run time (eval)"),
    (r"createElement\(\s*['\"]script['\"]\s*\)", 2, "loads more code from the internet"),
    (r"document\.cookie", 2, "reads cookies"),
    (r"type\s*=\s*['\"]?password|input\[type=password\]|querySelector\([^)]*password", 3, "looks at password fields"),
    (r"addEventListener\(\s*['\"]key(down|up|press)['\"]", 1, "listens to the keyboard"),
    (r"GM_xmlhttpRequest|XMLHttpRequest|fetch\s*\(|navigator\.sendBeacon|new\s+WebSocket", 1, "sends data to servers"),
    (r"atob\s*\(|String\.fromCharCode|\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){6,}", 2, "hides its code (obfuscation)"),
    (r"localStorage|sessionStorage|indexedDB", 1, "reads saved site data"),
    (r"chrome\.(webRequest|cookies|history|tabs|debugger|management|proxy)|nativeMessaging", 2, "asks for powerful browser permissions"),
]


def analyze_extension(entry):
    """-> (level, [reasons]). Heuristic only."""
    code = str(entry.get("code", ""))
    match = str(entry.get("match", "*")).strip()
    score, why = 0, []
    for rx, pts, text in RISK_RULES:
        if re.search(rx, code):
            score += pts; why.append(text)
    if match in ("*", "", "<all_urls>", "*://*/*", "http*://*/*", "*://*/") or "all_urls" in match:
        score += 1; why.append("runs on every website")
    sends = any("sends data" in w for w in why)
    steals = any(w in why for w in ("reads cookies", "looks at password fields"))
    if sends and steals:
        score += 3; why.append("can read private data AND send it out")
    level = BAD if score >= 7 else WARN if score >= 3 else OK
    return level, why


def check_extensions(extensions, scripts):
    res = []
    items = [("Extension", e) for e in extensions] + [("User script", s) for s in scripts]
    if not items:
        return [(OK, "Extensions", "No extensions or user scripts installed.")]
    risky = 0
    for kind, e in items:
        if not e.get("enabled", True):
            continue
        lvl, why = analyze_extension(e)
        if lvl != OK:
            risky += 1
            res.append((lvl, "%s: %s" % (kind, e.get("name", "?")), "Could be risky - it " + "; ".join(why[:4]) + ". Remove it if you do not know it."))
    if not risky:
        res.append((OK, "Extensions", "%d installed, nothing suspicious found (this is a quick code check, not a virus scan)." % len(items)))
    return res


def check_version(current, fetch_page, best_valid_update):
    try:
        page = fetch_page()
        info = best_valid_update(page, current)
        if info:
            return [(WARN, "Browser version", "Version %s is available (you have %s). Update for the latest security fixes." % (info["version"], current))]
        return [(OK, "Browser version", "You have the newest version (%s)." % current)]
    except Exception as ex:
        return [(INFO, "Browser version", "Could not check for updates (%s)." % type(ex).__name__)]


SETTING_CHECKS = [
    ("https_only", True, "HTTPS-only mode", "Turn on 'HTTPS only' so pages are never opened without encryption."),
    ("tracking_protection", True, "Tracker protection", "Turn on tracker protection."),
    ("ad_blocker", True, "Ad blocker", "Turn on the ad blocker (it also stops many harmful ads)."),
    ("block_popups", True, "Pop-up blocker", "Turn on the pop-up blocker."),
    ("safe_browsing", True, "Safe browsing", "Turn on safe browsing warnings."),
]


def check_settings(settings):
    res, bad = [], 0
    for key, want, title, hint in SETTING_CHECKS:
        if key not in settings and key != "https_only":
            continue
        if bool(settings.get(key, False)) == want:
            res.append((OK, title, "On."))
        else:
            bad += 1
            res.append((WARN, title, "Off. " + hint))
    return res


def run_all(*, passwords, extensions, scripts, settings, current_version, fetch_page, best_valid_update, fetch=default_fetch, progress=None):
    out = []

    def step(name, fn):
        if progress:
            progress(name)
        out.extend(fn())
    step("Checking protection settings…", lambda: check_settings(settings))
    step("Checking the browser version…", lambda: check_version(current_version, fetch_page, best_valid_update))
    step("Checking extensions…", lambda: check_extensions(extensions, scripts))
    step("Checking passwords (only a 5-character fingerprint leaves this computer)…", lambda: check_passwords(passwords, fetch)[0])
    return out


def summary(results):
    bad = sum(1 for r in results if r[0] == BAD)
    warn = sum(1 for r in results if r[0] == WARN)
    return bad, warn
