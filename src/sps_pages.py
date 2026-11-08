"""
SPS internal pages (pure HTML generators, no Qt): network error pages, certificate warnings, malicious-site warnings
and the 'Safe video player' block page.  Every dynamic value is HTML-escaped; the failed URL is passed to the page's
script through JSON with '<' escaped, so a hostile URL can never inject markup or script.
"""
import html as _html
import json as _json
import re as _re
import urllib.parse as _up

# Chromium net error code -> (category, title, explanation, tips)
_CATS = {
    "offline": ("No internet connection", "Your computer is not connected to the internet.",
                ["Check the network cable, Wi-Fi or mobile data.", "Restart your router or modem.", "This page reloads by itself when you are back online."]),
    "dns": ("This site can't be found", "The server's address could not be looked up (DNS).",
            ["Check that the address is spelled correctly.", "Try again in a few minutes.", "Check your DNS / proxy / VPN settings."]),
    "refused": ("The site refused to connect", "The server is reachable but it did not accept the connection.",
                ["The site may be down for maintenance.", "Check that a firewall or antivirus is not blocking it."]),
    "timeout": ("The site took too long to respond", "The connection was lost or the server did not answer in time.",
                ["Check your internet connection and try again.", "The site may be overloaded right now."]),
    "reset": ("The connection was interrupted", "The connection was reset while the page was loading.",
              ["Reload the page.", "If it keeps happening, try another network."]),
    "ssl": ("A secure connection could not be made", "The site uses encryption (HTTPS) in a way this browser cannot use safely.",
            ["The site may be configured incorrectly.", "Do not enter passwords on this site."]),
    "cert": ("Your connection is not private", "", []),
    "redirects": ("Too many redirects", "The site keeps sending the browser from page to page.",
                  ["Clear the cookies for this site and try again."]),
    "blocked": ("This page was blocked", "SPS Browser blocked this address.", ["Check Settings > Security if you did not expect this."]),
    "badurl": ("The address is not valid", "The browser cannot open this kind of address.", ["Check the address for typing mistakes."]),
    "generic": ("This page can't be reached", "Something went wrong while loading the page.", ["Reload the page.", "Try again later."]),
}
_CODE_CAT = {
    -106: "offline", -21: "offline", -105: "dns", -137: "dns", -801: "dns", -102: "refused", -118: "timeout", -7: "timeout", -109: "timeout",
    -101: "reset", -100: "reset", -324: "reset", -104: "reset", -107: "ssl", -113: "ssl", -501: "ssl", -310: "redirects",
    -20: "blocked", -22: "blocked", -300: "badurl", -301: "badurl", -302: "badurl",
}


def error_category(code, domain=""):
    """-> category name, or None when SPS should NOT replace the page (user aborted, server-side HTTP errors ...)."""
    try:
        code = int(code)
    except Exception:
        return "generic"
    if code in (-3, 0):
        return None
    # Qt6 names the HTTP domain "HttpStatusCodeDomain" (Qt5: "HttpErrorDomain"). A server's own answer - Google's "are you a robot?"
    # check (429), a 404 or 500 page - must be SHOWN as the site sent it, never swapped for "This page can't be reached".
    if domain in ("HttpErrorDomain", "HttpStatusCodeDomain", "NoErrorDomain") or "http" in str(domain).lower() or 400 <= code <= 599:
        return None
    if domain == "CertificateErrorDomain" or -220 <= code <= -200:
        return "cert"
    if domain == "DnsErrorDomain":
        return "dns"
    return _CODE_CAT.get(code, "generic")


def _esc(x):
    return _html.escape(str(x), quote=True)


def _js_str(x):
    return _json.dumps(str(x)).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _theme(dark):
    if dark:
        return dict(bg="#16181d", card="#1f2229", fg="#e8eaed", muted="#9aa0a6", line="#3c4043", accent="#8ab4f8")
    return dict(bg="#f6f8fc", card="#ffffff", fg="#202124", muted="#5f6368", line="#dadce0", accent="#1a73e8")


def _shell(title, body, dark, danger=False):
    t = _theme(dark)
    top = "#b3261e" if danger else t["accent"]
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><title>%s</title>"
            "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:\">"
            "<style>body{margin:0;background:%s;color:%s;font-family:'Segoe UI',system-ui,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center}"
            ".c{max-width:640px;width:92%%;background:%s;border:1px solid %s;border-top:6px solid %s;border-radius:14px;padding:34px 38px;box-shadow:0 4px 24px rgba(0,0,0,.12)}"
            "h1{font-size:26px;margin:6px 0 10px}p{line-height:1.55;color:%s}code{background:rgba(127,127,127,.18);padding:2px 6px;border-radius:5px;word-break:break-all}"
            "ul{color:%s;line-height:1.7}.b{display:inline-block;margin:6px 10px 0 0;padding:10px 20px;border-radius:8px;font-weight:600;text-decoration:none;border:1px solid %s;cursor:pointer;font-size:14px;color:%s;background:transparent}"
            ".p{background:%s;color:#fff;border-color:%s}.d{color:#b3261e;border-color:#b3261e}details{margin-top:18px;color:%s}summary{cursor:pointer;color:%s}"
            ".ic{font-size:46px}.code{font-size:12px;color:%s;margin-top:18px}</style></head><body><div class='c'>%s</div></body></html>"
            % (_esc(title), t["bg"], t["fg"], t["card"], t["line"], top, t["muted"], t["muted"], t["line"], t["fg"], top, top, t["muted"], t["accent"], t["muted"], body))


def error_page_html(url, code, domain="", detail="", dark=True):
    cat = error_category(code, domain) or "generic"
    title, text, tips = _CATS[cat]
    host = _up.urlsplit(url).hostname or url
    icon = {"offline": "&#128246;", "dns": "&#128269;", "refused": "&#9940;", "timeout": "&#8987;", "reset": "&#128260;", "ssl": "&#128274;",
            "blocked": "&#9940;"}.get(cat, "&#9888;&#65039;")
    lis = "".join("<li>%s</li>" % _esc(t) for t in tips)
    body = ("<div class='ic'>%s</div><h1>%s</h1><p><b>%s</b></p><p>%s</p><ul>%s</ul>"
            "<a class='b p' href='#' id='r'>Reload</a>"
            "<div class='code'>Error code: %s%s</div>"
            "<script>var U=%s;document.getElementById('r').addEventListener('click',function(e){e.preventDefault();location.replace(U)});"
            "%s</script>"
            % (icon, _esc(title), _esc(host), _esc(text), lis, _esc(code), (" - " + _esc(detail)) if detail else "", _js_str(url),
               "window.addEventListener('online',function(){location.replace(U)});" if cat in ("offline", "dns", "timeout") else ""))
    return _shell(title, body, dark)


def cert_page_html(url, desc="", overridable=True, dark=True):
    host = _up.urlsplit(url).hostname or url
    proceed = ("<a class='b d' href='sps://proceed-unsafe?u=%s'>Proceed to %s (unsafe)</a>" % (_esc(_up.quote(url, safe="")), _esc(host))
               if overridable else "<p>The website's owner has made this site impossible to open with a certificate error.</p>")
    body = ("<div class='ic'>&#128274;</div><h1>Your connection is not private</h1>"
            "<p>Attackers might be trying to steal your information from <b>%s</b> (for example passwords, messages or credit cards).</p>"
            "<a class='b p' href='#' onclick='history.length>1?history.back():window.close();return false'>Back to safety</a>"
            "<details><summary>Advanced</summary><p>%s</p><p>%s</p></details>"
            % (_esc(host), _esc(desc or "The site's security certificate could not be verified."), proceed))
    return _shell("Your connection is not private", body, dark, danger=True)


_THREAT_TEXT = {
    "malware": ("Dangerous website: malware", "This website is on a list of sites that spread harmful software. Opening it could infect your computer."),
    "phishing": ("Dangerous website: phishing", "This website looks like a fake page that tries to steal passwords, bank details or other private information."),
    "scam": ("Suspicious website", "This website looks like a scam or a copy of a well-known brand. Do not enter personal information or payments."),
}


def threat_page_html(url, kind, reason="", dark=True):
    title, text = _THREAT_TEXT.get(kind, _THREAT_TEXT["scam"])
    host = _up.urlsplit(url).hostname or url
    body = ("<div class='ic'>&#128683;</div><h1>%s</h1><p><b>%s</b></p><p>%s</p>"
            "<a class='b p' href='#' onclick='history.length>1?history.back():window.close();return false'>Back to safety</a>"
            "<details><summary>Details</summary><p>%s</p>"
            "<p>If you understand the risk and still want to open it, you can continue. SPS Browser will not ask again for this site until you restart.</p>"
            "<a class='b d' href='sps://proceed-threat?u=%s'>Continue anyway (not recommended)</a></details>"
            % (_esc(title), _esc(host), _esc(text), _esc(reason or "Matched SPS Browser's threat lists."), _esc(_up.quote(url, safe=""))))
    return _shell(title, body, dark, danger=True)


def adult_page_html(url, dark=True):
    host = _up.urlsplit(url).hostname or url
    body = ("<div class='ic'>&#128737;&#65039;</div><h1>Blocked by Safe video player</h1><p><b>%s</b></p>"
            "<p>This page is for adults. Safe video player is switched on in this browser, so it was not opened.</p>"
            "<a class='b p' href='#' onclick='history.length>1?history.back():window.close();return false'>Go back</a>"
            "<p style='font-size:12px'>An adult can switch Safe video player off in Settings &gt; Security (a PIN may be needed).</p>" % _esc(host))
    return _shell("Blocked by Safe video player", body, dark)
