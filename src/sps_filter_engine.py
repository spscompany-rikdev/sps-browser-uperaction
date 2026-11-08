"""
SPS filter engine  -  ad blocking, tracker blocking, cosmetic filtering, threat / adult host lists.
Pure Python (no Qt), so it can be unit-tested.  Understands the Adblock Plus / uBlock Origin list syntax that matters:

    ||example.com^            host-anchored rule          @@||example.com^     exception
    |http://  ...|            start / end anchors         *  and  ^             wildcard / separator
    /regex/                   regular expression          $third-party,$script,$image,$domain=a.com|~b.com,$important ...
    ##.ad-banner              generic cosmetic rule       example.com##.ad     site-specific      #@#  cosmetic exception

Rules with options the engine cannot honour (redirect=, removeparam=, csp=, scriptlets ...) are skipped, never half-applied.
"""
import os
import re
import time
import threading
import urllib.parse
import urllib.request
from collections import OrderedDict

_TYPE_ALIASES = {
    "script": "script", "image": "image", "stylesheet": "stylesheet", "css": "stylesheet", "xmlhttprequest": "xhr", "xhr": "xhr",
    "subdocument": "subdocument", "frame": "subdocument", "media": "media", "font": "font", "websocket": "websocket",
    "ping": "ping", "object": "object", "other": "other", "document": "document", "doc": "document",
}
_IGNORED_OPTS = {"match-case", "all", "3p-only"}
_UNSUPPORTED_PREFIX = ("redirect", "removeparam", "queryprune", "csp", "replace", "rewrite", "popup", "popunder", "generichide", "ghide",
                       "genericblock", "elemhide", "ehide", "specifichide", "shide", "cname", "denyallow", "header", "permissions",
                       "to=", "from=", "method=", "badfilter", "inline-script", "inline-font", "empty", "mp4", "noop", "1p-only")
_MULTI_TLD = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.in", "net.in", "org.in", "co.jp", "ne.jp", "or.jp",
              "com.br", "com.cn", "com.mx", "com.tr", "com.sg", "co.nz", "co.za", "com.hk", "com.tw", "co.kr", "com.ar", "com.pk", "com.bd"}
_SEP_CLASS = r"(?:[^\w\-.%]|$)"
_TOKEN_RX = re.compile(r"[a-z0-9%]{3,}")
_HOST_OK = re.compile(r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)+$")
_SAFE_SELECTOR = re.compile(r"^[^{};\\]{1,300}$")


def reg_domain(host):
    host = (host or "").lower().strip(".")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if ".".join(parts[-2:]) in _MULTI_TLD and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _host_chain(host):
    h = host
    while h:
        yield h
        i = h.find(".")
        h = h[i + 1:] if i != -1 else ""


def _glob_to_regex(p):
    out = []
    for ch in p:
        if ch == "*":
            out.append(".*")
        elif ch == "^":
            out.append(_SEP_CLASS)
        else:
            out.append(re.escape(ch))
    return "".join(out)


def _best_token(pat, start=False, end=False):
    """Longest run of letters/digits in the pattern that is bounded on both sides by a real character
    (not by '*' and not by an open pattern edge) - only such runs are guaranteed to appear as a whole token in a matching URL."""
    best = ""
    for m in re.finditer(r"[a-z0-9%]+", pat.lower()):
        left_ok = (m.start() > 0 and pat[m.start() - 1] != "*") or (m.start() == 0 and start)
        right_ok = (m.end() < len(pat) and pat[m.end()] != "*") or (m.end() == len(pat) and end)
        if left_ok and right_ok and len(m.group()) >= 3 and len(m.group()) > len(best):
            best = m.group()
    return best


def _regex_hint(src):
    """A literal piece (>=3 chars) every match of the regex must contain - used to skip the regex quickly."""
    runs, cur, i = [], [], 0
    while i < len(src):
        c = src[i]
        if c == "\\" and i + 1 < len(src):
            n = src[i + 1]
            if n in "/.-:_=?&%#":
                cur.append(n); i += 2
            else:
                runs.append("".join(cur)); cur = []; i += 2
            if i < len(src) and src[i] in "*?{":
                cur = cur[:-1] if cur else cur
            continue
        if c in "[](){}*+?|^$.":
            runs.append("".join(cur)); cur = []; i += 1; continue
        cur.append(c.lower()); i += 1
        if i < len(src) and src[i] in "*?{":
            cur = cur[:-1]
    runs.append("".join(cur))
    runs = [r for r in runs if len(r) >= 3]
    return max(runs, key=len) if runs else ""


class NetRule:
    __slots__ = ("raw", "exception", "important", "types", "not_types", "third", "domains", "not_domains",
                 "host", "rest", "literal", "start", "end", "regex_src", "_rx", "hint")

    def __init__(self):
        self.exception = False; self.important = False
        self.types = None; self.not_types = None; self.third = None
        self.domains = None; self.not_domains = None
        self.host = ""; self.rest = ""; self.literal = None
        self.start = False; self.end = False; self.regex_src = None; self._rx = None; self.hint = ""

    # ---- pattern test ------------------------------------------------------------------------------
    def _regex(self):
        if self._rx is None:
            if self.regex_src is not None:
                src = self.regex_src
            else:
                src = ("^" if self.start else "") + _glob_to_regex(self.rest) + ("$" if self.end else "")
            try:
                self._rx = re.compile(src)
            except re.error:
                self._rx = re.compile(r"(?!x)x")        # never matches
        return self._rx

    def pattern_matches(self, url, host_end):
        if self.host:                                    # ||host^rest  - the rest must match right after the host name
            if not self.rest:
                return True
            if self.literal is not None and not self.end:
                return url.startswith(self.literal, host_end)
            src = _glob_to_regex(self.rest) + ("$" if self.end else "")        # match(url, pos) already anchors at pos
            rx = self._rx or re.compile(src)
            self._rx = rx
            return rx.match(url, host_end) is not None
        if self.regex_src is not None:
            if self.hint and self.hint not in url:
                return False
            return self._regex().search(url) is not None
        if self.literal is not None and not self.start and not self.end:
            return self.literal in url
        if self.start:
            return self._regex().match(url) is not None
        return self._regex().search(url) is not None

    def options_match(self, rtype, third, src_host):
        if self.types is not None and rtype not in self.types:
            return False
        if self.not_types is not None and rtype in self.not_types:
            return False
        if self.third is not None and third is not None and self.third != third:
            return False
        if self.domains is not None or self.not_domains is not None:
            sh = src_host or ""
            if self.not_domains and any(sh == d or sh.endswith("." + d) for d in self.not_domains):
                return False
            if self.domains and not any(sh == d or sh.endswith("." + d) for d in self.domains):
                return False
        return True


def parse_net_rule(line):
    """-> NetRule or None (comment, cosmetic, unsupported or invalid)."""
    line = line.strip()
    if not line or line[0] in "![" or len(line) > 1200:
        return None
    if "##" in line or "#@#" in line or "#?#" in line or "#$#" in line or "#%#" in line or "#+js" in line:
        return None
    r = NetRule(); r.raw = line
    if line.startswith("@@"):
        r.exception = True; line = line[2:]
    opts = ""
    idx = line.rfind("$")
    if idx != -1 and not (line.startswith("/") and line.rfind("/") > idx):
        cand = line[idx + 1:]
        if re.fullmatch(r"[\w~=,|.\-:/*]+", cand):
            line, opts = line[:idx], cand
    if opts:
        for o in opts.split(","):
            o = o.strip()
            if not o:
                continue
            neg = o.startswith("~"); name = o.lstrip("~").lower()
            if name.startswith("domain="):
                for d in name[7:].split("|"):
                    d = d.strip().lstrip(".")
                    if not d:
                        continue
                    if d.startswith("~"):
                        r.not_domains = (r.not_domains or []) + [d[1:]]
                    else:
                        r.domains = (r.domains or []) + [d]
            elif name in ("third-party", "3p"):
                r.third = (not neg)
            elif name in ("first-party", "1p"):
                r.third = neg
            elif name == "important":
                r.important = True
            elif name in _TYPE_ALIASES:
                t = _TYPE_ALIASES[name]
                if neg:
                    r.not_types = (r.not_types or set()) | {t}
                else:
                    r.types = (r.types or set()) | {t}
            elif name in _IGNORED_OPTS:
                continue
            else:
                return None                                  # unknown / unsupported option (redirect=, removeparam=, csp= ...) -> skip the whole rule
    if line.startswith("/") and line.endswith("/") and len(line) > 2:
        src = line[1:-1]
        if len(src) > 220 or re.search(r"\([^)]*[+*][^)]*\)[+*]", src):
            return None                                      # too long / catastrophic-backtracking shape
        try:
            re.compile(src)
        except re.error:
            return None
        r.regex_src = src
        r.hint = _regex_hint(src)
        return r
    if line.startswith("||"):
        body = line[2:]
        m = re.match(r"^([a-z0-9.\-]+)(.*)$", body, re.I | re.S)
        if not m or not _HOST_OK.match(m.group(1).lower().strip(".")):
            return None
        r.host = m.group(1).lower().strip("."); rest = m.group(2)
        if rest.endswith("|"):
            r.end = True; rest = rest[:-1]
        r.rest = rest.lower()
        if r.rest in ("^", "/", ""):
            r.rest = "" if r.rest == "" else r.rest
        if r.rest and not re.search(r"[*^]", r.rest):
            r.literal = r.rest
        elif r.rest in ("^",):
            r.rest = "^"
        return r
    if line.startswith("|") and not line.startswith("||"):
        r.start = True; line = line[1:]
    if line.endswith("|"):
        r.end = True; line = line[:-1]
    line = line.lower()
    if not line or line in ("*", "^"):
        return None
    r.rest = line
    if not re.search(r"[*^]", line):
        r.literal = line
    return r


class FilterEngine:
    """Network + cosmetic rules.  Thread-safe for matching (read-only after loading)."""
    CACHE_SIZE = 6000

    def __init__(self):
        self.reset()

    def reset(self):
        self.block_host = {}; self.block_tok = {}; self.block_other = []
        self.allow_host = {}; self.allow_tok = {}; self.allow_other = []
        self.generic_css = []; self.site_css = {}; self.css_exceptions = {}
        self.rule_count = 0; self.cosmetic_count = 0
        self._cache = OrderedDict(); self._lock = threading.Lock()

    # ---- loading ------------------------------------------------------------------------------
    def load_text(self, text):
        n = 0
        for line in (text or "").splitlines():
            if self._add_line(line):
                n += 1
        return n

    def _add_line(self, line):
        line = line.strip()
        if not line or line[0] == "!" or line[0] == "[":
            return False
        if "##" in line or "#@#" in line:
            return self._add_cosmetic(line)
        r = parse_net_rule(line)
        if r is None:
            return False
        hidx, tidx, oth = (self.allow_host, self.allow_tok, self.allow_other) if r.exception else (self.block_host, self.block_tok, self.block_other)
        if r.host:
            hidx.setdefault(r.host, []).append(r)
        elif r.regex_src is not None:
            oth.append(r)                                  # regex rules: cheap literal pre-check (hint) instead of an index
        else:
            tok = _best_token(r.rest, r.start, r.end)
            if tok:
                tidx.setdefault(tok, []).append(r)
            else:
                oth.append(r)
        self.rule_count += 1
        return True

    def _add_cosmetic(self, line):
        exc = "#@#" in line
        sep = "#@#" if exc else "##"
        doms, sel = line.split(sep, 1)
        sel = sel.strip()
        if not sel or not _SAFE_SELECTOR.match(sel) or re.search(r"url\(|expression\(|@import|javascript:|:-abp-|:has-text|:xpath|:matches-css|:style\(|:remove\(", sel, re.I):
            return False
        dl = [d.strip().lower() for d in doms.split(",") if d.strip()]
        pos = [d for d in dl if not d.startswith("~")]; neg = [d[1:] for d in dl if d.startswith("~")]
        if exc:
            for d in (pos or ["*"]):
                self.css_exceptions.setdefault(d, set()).add(sel)
            return True
        if not pos:
            if len(self.generic_css) < 4000:
                self.generic_css.append((sel, tuple(neg)))
        else:
            for d in pos:
                self.site_css.setdefault(d, []).append(sel)
        self.cosmetic_count += 1
        return True

    # ---- matching ------------------------------------------------------------------------------
    def _find(self, hidx, tidx, oth, url, host, host_end, rtype, third, src_host):
        for h in _host_chain(host):
            for r in hidx.get(h, ()):
                if r.options_match(rtype, third, src_host) and r.pattern_matches(url, host_end):
                    return r
        toks = set(_TOKEN_RX.findall(url))
        if len(toks) > 150:
            toks = set(list(toks)[:150])
        for t in toks:
            for r in tidx.get(t, ()):
                if r.options_match(rtype, third, src_host) and r.pattern_matches(url, 0):
                    return r
        for r in oth:
            if r.options_match(rtype, third, src_host) and r.pattern_matches(url, 0):
                return r
        return None

    def match(self, url, source_host="", rtype="other", third=None):
        """-> (blocked: bool, rule_text: str)"""
        key = (url, source_host, rtype, third)
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
                return hit
        res = self._match(url, source_host, rtype, third)
        with self._lock:
            self._cache[key] = res
            if len(self._cache) > self.CACHE_SIZE:
                self._cache.popitem(last=False)
        return res

    def _match(self, url, source_host, rtype, third):
        low = url.lower()
        try:
            p = urllib.parse.urlsplit(low)
            host = (p.hostname or "").strip(".")
        except Exception:
            return (False, "")
        if not host:
            return (False, "")
        src = (source_host or "").lower().strip(".")
        if third is None:
            third = bool(src) and reg_domain(src) != reg_domain(host)
        i = low.find(host)
        host_end = (i + len(host)) if i != -1 else 0
        blk = self._find(self.block_host, self.block_tok, self.block_other, low, host, host_end, rtype, third, src)
        if blk is None:
            return (False, "")
        if not blk.important:
            ex = self._find(self.allow_host, self.allow_tok, self.allow_other, low, host, host_end, rtype, third, src)
            if ex is not None:
                return (False, ex.raw)
        return (True, blk.raw)

    # ---- cosmetic --------------------------------------------------------------------------------
    def cosmetic_css(self, host, limit=2500):
        host = (host or "").lower().strip(".")
        if not host:
            return ""
        exc = set(self.css_exceptions.get("*", ()))
        for h in _host_chain(host):
            exc |= self.css_exceptions.get(h, set())
        sels = []
        for sel, neg in self.generic_css:
            if sel in exc or any(host == d or host.endswith("." + d) for d in neg):
                continue
            sels.append(sel)
        for h in _host_chain(host):
            for sel in self.site_css.get(h, ()):
                if sel not in exc:
                    sels.append(sel)
        sels = sels[:limit]
        if not sels:
            return ""
        chunks = []
        for i in range(0, len(sels), 40):                    # one bad selector must not kill the others
            chunks.append(",".join(sels[i:i + 40]) + "{display:none!important;visibility:hidden!important}")
        return "\n".join(chunks)


# ═══════════════════════════════════════════════════════════════
#  host lists (malware / phishing / adult)
# ═══════════════════════════════════════════════════════════════
class HostSet:
    def __init__(self):
        self._s = set()

    def __len__(self):
        return len(self._s)

    def add(self, host):
        h = (host or "").strip().lower().strip(".")
        if _HOST_OK.match(h):
            self._s.add(h)

    def contains(self, host):
        h = (host or "").lower().strip(".")
        return any(x in self._s for x in _host_chain(h))

    def load_text(self, text):
        n = 0
        for line in (text or "").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("||"):
                line = line[2:].split("^", 1)[0].split("/", 1)[0]
                self.add(line); n += 1; continue
            parts = line.split()
            h = parts[-1] if parts and parts[0] in ("0.0.0.0", "127.0.0.1", "::1", "::") else parts[0]
            if "://" in h:
                try: h = urllib.parse.urlsplit(h).hostname or ""
                except Exception: continue
            if h and h not in ("localhost", "local", "broadcasthost", "ip6-localhost", "ip6-loopback", "0.0.0.0"):
                self.add(h); n += 1
        return n


_ADULT_STRONG = ("porn", "xvideos", "xnxx", "xhamster", "redtube", "youporn", "spankbang", "brazzers", "chaturbate", "stripchat",
                 "livejasmin", "bongacams", "onlyfans", "fansly", "rule34", "nhentai", "hentai", "hqporner", "eporner", "tnaflix",
                 "tube8", "camsoda", "myfreecams", "xxx", "sexcam", "camgirl", "erotic", "xtube", "pornhub", "motherless", "efukt")
_ADULT_TOKENS = {"sex", "nude", "nudes", "nsfw", "fetish", "milf", "hentai", "xxx", "porno"}
ADULT_SEED_HOSTS = ("pornhub.com", "xvideos.com", "xnxx.com", "xhamster.com", "redtube.com", "youporn.com", "spankbang.com", "brazzers.com",
                    "chaturbate.com", "stripchat.com", "livejasmin.com", "bongacams.com", "onlyfans.com", "fansly.com", "rule34.xxx",
                    "nhentai.net", "hqporner.com", "eporner.com", "tnaflix.com", "tube8.com", "camsoda.com", "myfreecams.com",
                    "motherless.com", "xtube.com", "efukt.com", "beeg.com", "porntrex.com", "pornone.com", "txxx.com", "hclips.com",
                    "thumbzilla.com", "pornhubpremium.com", "xvideos2.com", "xnxx.tv", "xhamster2.com", "e-hentai.org", "gelbooru.com",
                    "erome.com", "pornpics.com", "sex.com", "porn.com", "naughtyamerica.com", "realitykings.com", "bangbros.com")


def looks_adult_host(host):
    h = (host or "").lower().strip(".")
    if not h:
        return False
    flat = h.replace("-", "").replace(".", "")
    if any(k in flat for k in _ADULT_STRONG):
        return True
    toks = set(re.split(r"[.\-_]", h))
    return bool(toks & _ADULT_TOKENS)


# ═══════════════════════════════════════════════════════════════
#  list downloading (background)
# ═══════════════════════════════════════════════════════════════
FILTER_LIST_SOURCES = {
    "easylist.txt":      ("https://easylist.to/easylist/easylist.txt", "net"),
    "easyprivacy.txt":   ("https://easylist.to/easylist/easyprivacy.txt", "net"),
    "ublock-filters.txt": ("https://ublockorigin.github.io/uAssets/filters/filters.txt", "net"),
    "ublock-privacy.txt": ("https://ublockorigin.github.io/uAssets/filters/privacy.txt", "net"),
    "ublock-badware.txt": ("https://ublockorigin.github.io/uAssets/filters/badware.txt", "net"),
    "urlhaus-hosts.txt": ("https://urlhaus.abuse.ch/downloads/hostfile/", "malware"),
    "phishing-army.txt": ("https://phishing.army/download/phishing_army_blocklist.txt", "phishing"),
    "adult-hosts.txt":   ("https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/porn-only/hosts", "adult"),
}
MAX_LIST_BYTES = 12 * 1024 * 1024


def download_list(url, dest, timeout=25):
    """HTTPS only, size-capped, atomic. Returns (ok, message). The old file is kept if anything looks wrong."""
    if not url.lower().startswith("https://"):
        return False, "only https lists are allowed"
    req = urllib.request.Request(url, headers={"User-Agent": "SPS-Browser-filter-updater/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(MAX_LIST_BYTES + 1)
    except Exception as e:
        return False, "download failed: %s" % e
    if len(data) > MAX_LIST_BYTES:
        return False, "list too large"
    text = data.decode("utf-8", "replace")
    if len(text) < 200 or "<html" in text[:500].lower():
        return False, "answer is not a filter list"
    tmp = dest + ".tmp"
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, dest)
    except Exception as e:
        return False, "could not save: %s" % e
    return True, "%d bytes" % len(data)


def load_all(folder, engine=None, malware=None, phishing=None, adult=None):
    """Load every known list file found in `folder` into the given engine / host sets. Returns a small report dict."""
    rep = {"net_rules": 0, "cosmetic": 0, "malware": 0, "phishing": 0, "adult": 0, "files": 0}
    for fname, (_url, kind) in FILTER_LIST_SOURCES.items():
        p = os.path.join(folder, fname)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception:
            continue
        rep["files"] += 1
        if kind == "net" and engine is not None:
            engine.load_text(text)
        elif kind == "malware" and malware is not None:
            rep["malware"] += malware.load_text(text)
        elif kind == "phishing" and phishing is not None:
            rep["phishing"] += phishing.load_text(text)
        elif kind == "adult" and adult is not None:
            rep["adult"] += adult.load_text(text)
    if engine is not None:
        rep["net_rules"] = engine.rule_count; rep["cosmetic"] = engine.cosmetic_count
    return rep
