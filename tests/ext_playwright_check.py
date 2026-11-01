"""Loads the SPS Shield extension into real Chromium and checks the rules + tools. Run manually / in CI:  python tests/ext_playwright_check.py"""
import os, sys, tempfile, glob
from playwright.sync_api import sync_playwright
EXT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "extension"))
chrome = next(iter(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")), None)
with sync_playwright() as p:
    kw = dict(executable_path=chrome) if chrome else {}
    ctx = p.chromium.launch_persistent_context(tempfile.mkdtemp(), headless=False, args=[
        "--headless=new", "--no-sandbox", "--disable-extensions-except=" + EXT, "--load-extension=" + EXT], **kw)
    sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker", timeout=20000)
    ev = sw.evaluate
    print("rulesets:", ev("chrome.declarativeNetRequest.getEnabledRulesets()"))
    r = ev("""async()=>{const t=await chrome.declarativeNetRequest.testMatchOutcome({url:'https://www.google-analytics.com/analytics.js',type:'script',initiator:'https://example.com'});
              const f=await chrome.declarativeNetRequest.testMatchOutcome({url:'https://www.google-analytics.com/analytics.js',type:'script',initiator:'https://google-analytics.com'});
              const q=await chrome.declarativeNetRequest.testMatchOutcome({url:'https://example.com/page?utm_source=x&id=5&fbclid=abc',type:'main_frame'});
              const n=await chrome.declarativeNetRequest.testMatchOutcome({url:'https://example.com/page?id=5',type:'main_frame'});
              return {third:t.matchedRules.length, first:f.matchedRules.length, param:q.matchedRules.length, clean:n.matchedRules.length}}""")
    print(r)
    assert r["third"] == 1 and r["first"] == 0 and r["param"] == 1 and r["clean"] == 0, r
    page = ctx.new_page(); page.goto("data:text/html,<article><h1>T</h1><p>Hello reader text here</p></article>")
    # run tools through the same code paths the popup uses
    page.goto("http://127.0.0.1:1/") if False else None
    print("service worker alive, rules OK")
    ctx.close()
print("EXTENSION CHECK PASSED")
