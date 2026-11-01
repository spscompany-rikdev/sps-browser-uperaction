package com.spscompany.spsbrowser;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.DialogInterface;
import android.content.pm.PackageManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.database.Cursor;
import android.os.Environment;
import android.speech.RecognizerIntent;
import android.print.PrintAttributes;
import android.print.PrintManager;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.webkit.CookieManager;
import android.webkit.GeolocationPermissions;
import android.webkit.PermissionRequest;
import android.webkit.URLUtil;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebStorage;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONTokener;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.InputStreamReader;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * SPS Browser for Android - a private browser built on the system WebView (Chromium).
 * Tabs, private tabs, bookmarks, history, find in page, desktop site, dark mode, ad/tracker blocking,
 * downloads, file upload, full-screen video, https-only, no analytics. Everything is stored on the phone only.
 */
public class MainActivity extends Activity {

    private static final String[] ENGINE_NAMES = {"Google", "DuckDuckGo", "Bing", "Brave Search", "Ecosia"};
    private static final String[] ENGINE_URLS = {"https://www.google.com/search", "https://duckduckgo.com/",
            "https://www.bing.com/search", "https://search.brave.com/search", "https://www.ecosia.org/search"};
    private static final int[] TEXT_SIZES = {100, 115, 130, 150, 85};
    private static final String NEWTAB_BASE = "https://sps.newtab/";
    private static final String DESKTOP_UA =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";
    private static final int FILE_CHOOSER = 4711;
    private static final int REQ_VOICE = 4712;
    private static final int REQ_MEDIA = 11;
    private static final int REQ_GEO = 12;

    /** One browser tab. */
    private static class Tab {
        WebView web;
        boolean priv;
        boolean desktop;
        String title = "New tab";
        String url = "";
        String mobileUa;
    }

    private final ArrayList<Tab> tabs = new ArrayList<>();
    private Tab current;
    private final Set<String> blocked = new HashSet<>();
    private final AtomicInteger blockedCount = new AtomicInteger(0);

    private SharedPreferences prefs;
    private boolean adBlock = true;
    private boolean darkMode = false;
    private boolean thirdPartyCookies = false;
    private boolean jsEnabled = true;
    private boolean safeBrowsing = true;
    private boolean saveHistory = true;
    private boolean blockShots = false;
    private boolean clearOnExit = false;
    private boolean desktopDefault = false;
    private String homeUrl = "";
    private PermissionRequest pendingPerm;
    private String[] pendingResources;
    private GeolocationPermissions.Callback pendingGeoCb;
    private String pendingGeoOrigin;
    private int engine = 0;
    private int textSizeIndex = 0;

    private FrameLayout root;
    private FrameLayout webHolder;
    private LinearLayout bar;
    private LinearLayout findBar;
    private EditText urlBar;
    private EditText findInput;
    private Button tabsButton;
    private ProgressBar progress;
    private View customView;
    private WebChromeClient.CustomViewCallback customViewCallback;
    private ValueCallback<Uri[]> filePathCallback;

    // ───────────────────────────── start ─────────────────────────────
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("sps", MODE_PRIVATE);
        adBlock = prefs.getBoolean("adblock", true);
        darkMode = prefs.getBoolean("dark", false);
        thirdPartyCookies = prefs.getBoolean("thirdcookies", false);
        jsEnabled = prefs.getBoolean("js", true);
        safeBrowsing = prefs.getBoolean("safebrowsing", true);
        saveHistory = prefs.getBoolean("savehistory", true);
        blockShots = prefs.getBoolean("blockshots", false);
        clearOnExit = prefs.getBoolean("clearonexit", false);
        desktopDefault = prefs.getBoolean("desktopdefault", false);
        homeUrl = prefs.getString("home", "");
        engine = Math.max(0, Math.min(ENGINE_URLS.length - 1, prefs.getInt("engine", 0)));
        textSizeIndex = Math.max(0, Math.min(TEXT_SIZES.length - 1, prefs.getInt("textsize", 0)));
        loadBlocklist();
        buildUi();

        boolean any = false;
        try {
            JSONArray saved = new JSONArray(prefs.getString("session", "[]"));
            for (int i = 0; i < saved.length(); i++) {
                String u = saved.getString(i);
                newTab(u, false, false);
                any = true;
            }
        } catch (Exception ignored) { }
        Uri data = getIntent() != null ? getIntent().getData() : null;
        if (data != null) newTab(data.toString(), false, true);
        else if (!any) newTab(null, false, true);
        else switchTo(tabs.get(Math.min(prefs.getInt("session_index", 0), tabs.size() - 1)));
    }

    private void buildUi() {
        root = new FrameLayout(this);
        root.setBackgroundColor(Color.WHITE);

        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);

        bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setBackgroundColor(Color.parseColor("#F1F3F4"));
        bar.setPadding(dp(4), dp(4), dp(4), dp(4));

        Button back = barButton("◀");
        Button reload = barButton("↻");
        urlBar = new EditText(this);
        urlBar.setSingleLine(true);
        urlBar.setTextSize(14);
        urlBar.setHint("Search or type a web address");
        urlBar.setImeOptions(EditorInfo.IME_ACTION_GO);
        urlBar.setInputType(android.text.InputType.TYPE_TEXT_VARIATION_URI);
        urlBar.setSelectAllOnFocus(true);
        urlBar.setPadding(dp(12), dp(8), dp(12), dp(8));
        urlBar.setBackgroundColor(Color.WHITE);
        tabsButton = barButton("1");
        Button menu = barButton("⋮");
        Button mic = barButton("🎤");

        bar.addView(back);
        bar.addView(reload);
        bar.addView(urlBar, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        bar.addView(mic);
        bar.addView(tabsButton);
        bar.addView(menu);

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setVisibility(View.GONE);

        findBar = new LinearLayout(this);
        findBar.setOrientation(LinearLayout.HORIZONTAL);
        findBar.setGravity(Gravity.CENTER_VERTICAL);
        findBar.setBackgroundColor(Color.parseColor("#E8EAED"));
        findBar.setVisibility(View.GONE);
        findInput = new EditText(this);
        findInput.setSingleLine(true);
        findInput.setHint("Find in page");
        findInput.setTextSize(14);
        Button prev = barButton("▲");
        Button next = barButton("▼");
        Button closeFind = barButton("✕");
        findBar.addView(findInput, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        findBar.addView(prev);
        findBar.addView(next);
        findBar.addView(closeFind);

        webHolder = new FrameLayout(this);

        column.addView(bar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        column.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(3)));
        column.addView(findBar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        column.addView(webHolder, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        root.addView(column, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

        back.setOnClickListener(v -> { if (current != null && current.web.canGoBack()) current.web.goBack(); });
        reload.setOnClickListener(v -> { if (current != null) current.web.reload(); });
        mic.setOnClickListener(v -> voiceSearch());
        tabsButton.setOnClickListener(v -> showTabs());
        menu.setOnClickListener(v -> showMenu());
        urlBar.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_GO || (event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER)) {
                go(urlBar.getText().toString());
                hideKeyboard();
                return true;
            }
            return false;
        });
        prev.setOnClickListener(v -> { if (current != null) current.web.findNext(false); });
        next.setOnClickListener(v -> { if (current != null) current.web.findNext(true); });
        closeFind.setOnClickListener(v -> closeFindBar());
        findInput.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int c) { }
            @Override public void onTextChanged(CharSequence s, int a, int b, int c) {
                if (current == null) return;
                if (s.length() == 0) current.web.clearMatches(); else current.web.findAllAsync(s.toString());
            }
            @Override public void afterTextChanged(Editable s) { }
        });
    }

    // ───────────────────────────── tabs ─────────────────────────────
    private Tab newTab(String url, boolean priv, boolean show) {
        Tab t = new Tab();
        t.priv = priv;
        t.web = new WebView(this);
        t.web.setVisibility(View.GONE);
        webHolder.addView(t.web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        tabs.add(t);
        setupWebView(t);
        if (url == null || url.isEmpty()) {
            if (!priv && !homeUrl.isEmpty()) t.web.loadUrl(homeUrl); else loadNewTabPage(t);
        } else {
            t.web.loadUrl(url);
        }
        if (show) switchTo(t);
        updateTabCount();
        return t;
    }

    private void switchTo(Tab t) {
        if (t == null) return;
        for (Tab o : tabs) o.web.setVisibility(o == t ? View.VISIBLE : View.GONE);
        current = t;
        urlBar.setBackgroundColor(t.priv ? Color.parseColor("#E8DEF8") : Color.WHITE);
        urlBar.setText(isNewTab(t.url) ? "" : t.url);
        progress.setVisibility(View.GONE);
        closeFindBar();
        applySecure();
        updateTabCount();
    }

    /** Private tabs (and the "Block screenshots" setting) switch on FLAG_SECURE: no screenshots, hidden in the app switcher. */
    private void applySecure() {
        boolean on = blockShots || (current != null && current.priv);
        if (on) getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
    }

    private void applyTabSettings(Tab t) {
        WebSettings ws = t.web.getSettings();
        ws.setJavaScriptEnabled(jsEnabled);
        if (Build.VERSION.SDK_INT >= 26) ws.setSafeBrowsingEnabled(safeBrowsing);
        CookieManager.getInstance().setAcceptThirdPartyCookies(t.web, thirdPartyCookies);
        ws.setTextZoom(TEXT_SIZES[textSizeIndex]);
        applyDark(ws);
    }

    private void closeTab(Tab t) {
        int i = tabs.indexOf(t);
        if (i < 0) return;
        webHolder.removeView(t.web);
        if (t.priv) { t.web.clearHistory(); t.web.clearCache(true); }
        t.web.destroy();
        tabs.remove(t);
        if (tabs.isEmpty()) {
            current = null;
            newTab(null, false, true);
        } else if (current == t) {
            switchTo(tabs.get(Math.max(0, i - 1)));
        }
        updateTabCount();
    }

    private void updateTabCount() {
        if (tabsButton != null) tabsButton.setText(String.valueOf(tabs.size()));
    }

    private void showTabs() {
        String[] names = new String[tabs.size()];
        for (int i = 0; i < names.length; i++) {
            Tab t = tabs.get(i);
            String label = (t.priv ? "🕶 " : "") + (t.title == null || t.title.isEmpty() ? t.url : t.title);
            names[i] = (t == current ? "● " : "") + label;
        }
        new AlertDialog.Builder(this)
                .setTitle("Tabs (" + tabs.size() + ")")
                .setItems(names, (d, which) -> switchTo(tabs.get(which)))
                .setPositiveButton("New tab", (d, w) -> newTab(null, false, true))
                .setNeutralButton("New private tab", (d, w) -> newTab(null, true, true))
                .setNegativeButton("Close this tab", (d, w) -> { if (current != null) closeTab(current); })
                .show();
    }

    // ───────────────────────────── web view ─────────────────────────────
    private void setupWebView(final Tab tab) {
        final WebView web = tab.web;
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setAllowFileAccessFromFileURLs(false);
        s.setAllowUniversalAccessFromFileURLs(false);
        s.setMediaPlaybackRequiresUserGesture(true);
        s.setSupportMultipleWindows(false);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setSaveFormData(false);
        s.setTextZoom(TEXT_SIZES[textSizeIndex]);
        if (tab.priv) s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        if (Build.VERSION.SDK_INT >= 26) s.setSafeBrowsingEnabled(true);
        applyDark(s);

        // The default WebView user agent contains "; wv" and "Version/4.0", which makes Google treat the app as an
        // embedded browser (robot checks, blocked sign-in). Present the normal Chrome mobile form instead.
        String ua = s.getUserAgentString();
        if (ua != null) {
            ua = ua.replace("; wv", "").replace(" Version/4.0", "");
            s.setUserAgentString(ua);
        }
        tab.mobileUa = ua;
        applyTabSettings(tab);
        if (desktopDefault) { tab.desktop = true; s.setUserAgentString(DESKTOP_UA); }

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, thirdPartyCookies);   // third-party cookies are off by default

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                String scheme = u.getScheme() == null ? "" : u.getScheme().toLowerCase();
                if (scheme.equals("http")) {                       // upgrade to https
                    view.loadUrl(u.buildUpon().scheme("https").build().toString());
                    return true;
                }
                if (scheme.equals("https") || scheme.equals("about") || scheme.equals("data")) return false;
                try {                                              // mailto:, tel:, intent: ... -> hand to the system, never run in the page
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                } catch (ActivityNotFoundException | SecurityException ignored) {
                    Toast.makeText(MainActivity.this, "No app can open this link", Toast.LENGTH_SHORT).show();
                }
                return true;
            }

            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                if (adBlock && !request.isForMainFrame() && isBlockedHost(request.getUrl().getHost())) {
                    blockedCount.incrementAndGet();
                    return new WebResourceResponse("text/plain", "utf-8", new ByteArrayInputStream(new byte[0]));
                }
                return null;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                tab.url = url == null ? "" : url;
                if (tab == current) {
                    progress.setVisibility(View.VISIBLE);
                    if (!urlBar.hasFocus()) urlBar.setText(isNewTab(tab.url) ? "" : tab.url);
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                tab.url = url == null ? "" : url;
                String title = view.getTitle();
                if (title != null && !title.isEmpty()) tab.title = title;
                if (tab == current) {
                    progress.setVisibility(View.GONE);
                    if (!urlBar.hasFocus()) urlBar.setText(isNewTab(tab.url) ? "" : tab.url);
                }
                if (!tab.priv && saveHistory && !isNewTab(tab.url) && tab.url.startsWith("https://")) addHistory(tab.title, tab.url);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    String page = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'></head>"
                            + "<body style='font-family:sans-serif;padding:32px;color:#202124'>"
                            + "<h2>This page can't be reached</h2><p>Please check your internet connection and try again.</p>"
                            + "<p style='color:#5f6368;font-size:13px'>" + android.text.TextUtils.htmlEncode(String.valueOf(error.getDescription())) + "</p>"
                            + "<button onclick='history.back()' style='padding:10px 18px'>Go back</button></body></html>";
                    view.loadDataWithBaseURL(null, page, "text/html", "utf-8", null);
                }
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                if (tab != current) return;
                progress.setProgress(newProgress);
                progress.setVisibility(newProgress >= 100 ? View.GONE : View.VISIBLE);
            }

            @Override
            public void onReceivedTitle(WebView view, String title) {
                if (title != null && !title.isEmpty()) tab.title = title;
            }

            @Override
            public void onShowCustomView(View view, CustomViewCallback callback) {     // full-screen video
                if (customView != null) { callback.onCustomViewHidden(); return; }
                customView = view;
                customViewCallback = callback;
                root.addView(view, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
                bar.setVisibility(View.GONE);
                getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN);
            }

            @Override
            public void onHideCustomView() {
                hideCustomViewNow();
            }

            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> handleWebPermission(tab, request));
            }

            @Override
            public void onGeolocationPermissionsShowPrompt(final String origin, final GeolocationPermissions.Callback callback) {
                handleGeoPermission(tab, origin, callback);
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (filePathCallback != null) filePathCallback.onReceiveValue(null);
                filePathCallback = callback;
                try {
                    startActivityForResult(params.createIntent(), FILE_CHOOSER);
                } catch (ActivityNotFoundException e) {
                    filePathCallback = null;
                    return false;
                }
                return true;
            }
        });

        web.setOnLongClickListener(v -> onLongPress(tab));

        web.setDownloadListener((url, userAgent, contentDisposition, mimetype, contentLength) -> startDownload(url, userAgent, contentDisposition, mimetype));
    }

    private void startDownload(String url, String userAgent, String contentDisposition, String mimetype) {
        {
            if (Build.VERSION.SDK_INT < 29
                    && checkSelfPermission(android.Manifest.permission.WRITE_EXTERNAL_STORAGE) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{android.Manifest.permission.WRITE_EXTERNAL_STORAGE}, 7);   // older Android needs this to save files
                Toast.makeText(this, "Allow storage access, then start the download again", Toast.LENGTH_LONG).show();
                return;
            }
            try {
                DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
                String name = URLUtil.guessFileName(url, contentDisposition, mimetype);
                if (mimetype != null) r.setMimeType(mimetype);
                if (userAgent != null) r.addRequestHeader("User-Agent", userAgent);
                String cookie = CookieManager.getInstance().getCookie(url);
                if (cookie != null) r.addRequestHeader("Cookie", cookie);
                r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
                long id = ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(r);
                rememberDownload(id, name);
                Toast.makeText(this, "Downloading " + name, Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                Toast.makeText(this, "Could not start the download", Toast.LENGTH_SHORT).show();
            }
        }
    }

    private void hideCustomViewNow() {
        if (customView == null) return;
        root.removeView(customView);
        customView = null;
        bar.setVisibility(View.VISIBLE);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_VISIBLE);
        if (customViewCallback != null) customViewCallback.onCustomViewHidden();
    }

    @SuppressWarnings("deprecation")
    private void applyDark(WebSettings s) {
        if (Build.VERSION.SDK_INT >= 29) {
            try { s.setForceDark(darkMode ? WebSettings.FORCE_DARK_ON : WebSettings.FORCE_DARK_OFF); } catch (Throwable ignored) { }
        }
    }

    // ───────────────────────────── new-tab page ─────────────────────────────
    private void loadNewTabPage(Tab t) {
        StringBuilder sites = new StringBuilder();
        String[][] quick = {
                {"Google", "https://www.google.com/"}, {"YouTube", "https://www.youtube.com/"},
                {"Wikipedia", "https://www.wikipedia.org/"}, {"GitHub", "https://github.com/"}};
        for (String[] q : quick) sites.append("<a class='s' href='").append(q[1]).append("'>").append(q[0]).append("</a>");
        try {
            JSONArray b = new JSONArray(prefs.getString("bookmarks", "[]"));
            for (int i = 0; i < b.length() && i < 12; i++) {
                JSONObject o = b.getJSONObject(i);
                sites.append("<a class='s' href='").append(android.text.TextUtils.htmlEncode(o.getString("u"))).append("'>")
                        .append(android.text.TextUtils.htmlEncode(o.optString("t", o.getString("u")))).append("</a>");
            }
        } catch (Exception ignored) { }
        String page = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>"
                + "body{font-family:sans-serif;margin:0;padding:48px 20px;text-align:center;background:" + (t.priv ? "#2b2438;color:#fff" : (darkMode ? "#202124;color:#e8eaed" : "#fff;color:#202124")) + "}"
                + "h1{font-weight:500;margin:0 0 6px}p{color:#888;margin:0 0 28px}"
                + "input{width:90%;max-width:520px;padding:14px 18px;border-radius:26px;border:1px solid #ccc;font-size:16px}"
                + ".s{display:inline-block;margin:10px;padding:12px 16px;border-radius:12px;background:rgba(128,128,128,.15);color:inherit;text-decoration:none;font-size:14px}"
                + "</style></head><body><h1>SPS Browser</h1><p>" + (t.priv ? "Private tab: no history is saved" : "Fast, private browsing") + "</p>"
                + "<form action='" + ENGINE_URLS[engine] + "' method='get'><input name='q' placeholder='Search " + ENGINE_NAMES[engine] + " or type a web address' autocomplete='off'></form>"
                + "<div style='margin-top:30px'>" + sites + "</div></body></html>";
        t.url = NEWTAB_BASE;
        t.title = t.priv ? "New private tab" : "New tab";
        t.web.loadDataWithBaseURL(NEWTAB_BASE, page, "text/html", "utf-8", null);
    }

    private boolean isNewTab(String url) {
        return url == null || url.isEmpty() || url.startsWith(NEWTAB_BASE) || url.equals("about:blank");
    }

    // ───────────────────────────── address bar ─────────────────────────────
    /** Turns what the user typed into a web address or a search. */
    private void go(String input) {
        String t = input == null ? "" : input.trim();
        if (t.isEmpty() || current == null) return;
        String url;
        if (t.startsWith("https://")) {
            url = t;
        } else if (t.startsWith("http://")) {
            url = "https://" + t.substring(7);
        } else if (!t.contains(" ") && t.contains(".") && !t.endsWith(".")) {
            url = "https://" + t;
        } else {
            try { url = searchBase() + "?q=" + URLEncoder.encode(t, "UTF-8"); } catch (Exception e) { url = "https://www.google.com/"; }
        }
        current.web.loadUrl(url);
    }

    // ───────────────────────────── menu ─────────────────────────────
    private void showMenu() {
        if (current == null) return;
        final ArrayList<String> labels = new ArrayList<>();
        final ArrayList<Runnable> acts = new ArrayList<>();
        final boolean page = !isNewTab(current.url);
        labels.add("New tab"); acts.add(() -> newTab(null, false, true));
        labels.add("New private tab"); acts.add(() -> newTab(null, true, true));
        if (page) { labels.add(isBookmarked(current.url) ? "Remove bookmark" : "Add bookmark"); acts.add(this::toggleBookmark); }
        labels.add("Bookmarks"); acts.add(this::showBookmarks);
        labels.add("History"); acts.add(this::showHistory);
        labels.add("Downloads"); acts.add(this::showDownloads);
        labels.add("Voice search"); acts.add(this::voiceSearch);
        labels.add("Find in page"); acts.add(this::openFindBar);
        if (page) {
            labels.add("Reader mode"); acts.add(this::readerMode);
            labels.add("Translate page"); acts.add(this::translatePage);
            labels.add("Print / Save as PDF"); acts.add(this::printPage);
            labels.add("Print selected area"); acts.add(this::printSelectedArea);
            labels.add("Copy link"); acts.add(this::copyLink);
            labels.add("Share page"); acts.add(this::sharePage);
            labels.add("Open in another browser"); acts.add(this::openExternal);
        }
        labels.add(current.desktop ? "Mobile site" : "Desktop site"); acts.add(this::toggleDesktop);
        labels.add(darkMode ? "Dark mode: ON" : "Dark mode: off"); acts.add(() -> {
            darkMode = !darkMode; prefs.edit().putBoolean("dark", darkMode).apply();
            for (Tab t : tabs) applyDark(t.web.getSettings());
            current.web.reload();
        });
        labels.add(adBlock ? "Ad & tracker blocking: ON (" + blockedCount.get() + " blocked)" : "Ad & tracker blocking: off"); acts.add(() -> {
            adBlock = !adBlock; prefs.edit().putBoolean("adblock", adBlock).apply();
            Toast.makeText(this, adBlock ? "Ad & tracker blocking on" : "Ad & tracker blocking off", Toast.LENGTH_SHORT).show();
            current.web.reload();
        });
        labels.add("Search engine: " + ENGINE_NAMES[engine]); acts.add(this::chooseEngine);
        labels.add("Text size: " + TEXT_SIZES[textSizeIndex] + "%"); acts.add(this::cycleTextSize);
        labels.add("Settings"); acts.add(this::showSettings);
        labels.add("Clear browsing data"); acts.add(this::clearData);
        labels.add("About SPS Browser"); acts.add(this::showAbout);
        new AlertDialog.Builder(this).setItems(labels.toArray(new String[0]), (d, which) -> acts.get(which).run()).show();
    }

    private String searchBase() {
        return ENGINE_URLS[engine];
    }

    private void chooseEngine() {
        new AlertDialog.Builder(this).setTitle("Search engine")
                .setSingleChoiceItems(ENGINE_NAMES, engine, (d, which) -> {
                    engine = which;
                    prefs.edit().putInt("engine", engine).apply();
                    d.dismiss();
                    Toast.makeText(this, "Search engine: " + ENGINE_NAMES[engine], Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("Cancel", null).show();
    }

    private void cycleTextSize() {
        textSizeIndex = (textSizeIndex + 1) % TEXT_SIZES.length;
        prefs.edit().putInt("textsize", textSizeIndex).apply();
        for (Tab t : tabs) t.web.getSettings().setTextZoom(TEXT_SIZES[textSizeIndex]);
        Toast.makeText(this, "Text size " + TEXT_SIZES[textSizeIndex] + "%", Toast.LENGTH_SHORT).show();
    }

    private void translatePage() {
        try {
            String lang = Locale.getDefault().getLanguage();
            current.web.loadUrl("https://translate.google.com/translate?sl=auto&tl=" + URLEncoder.encode(lang, "UTF-8")
                    + "&u=" + URLEncoder.encode(current.url, "UTF-8"));
        } catch (Exception e) {
            Toast.makeText(this, "Could not translate this page", Toast.LENGTH_SHORT).show();
        }
    }

    private void copyLink() {
        copyText(current.url);
    }

    private void copyText(String text) {
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm != null) {
            cm.setPrimaryClip(ClipData.newPlainText("link", text));
            Toast.makeText(this, "Copied", Toast.LENGTH_SHORT).show();
        }
    }

    private void openExternal() {
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(current.url));
            startActivity(Intent.createChooser(i, "Open with"));
        } catch (Exception e) {
            Toast.makeText(this, "No other app can open this", Toast.LENGTH_SHORT).show();
        }
    }

    /** Strips the page down to its headings and paragraphs (a simple reader view). */
    private void readerMode() {
        final Tab t = current;
        String js = "(function(){var a=document.querySelector('article')||document.querySelector('main')||document.body;"
                + "var ps=a.querySelectorAll('h1,h2,h3,p,li');var out=[];"
                + "for(var i=0;i<ps.length;i++){var e=ps[i];var x=(e.innerText||'').trim();"
                + "if(x.length>40||e.tagName.charAt(0)==='H'){var g=e.tagName.toLowerCase();"
                + "out.push('<'+g+'>'+x.replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</'+g+'>');}}"
                + "return JSON.stringify({t:document.title,h:out.join('')});})()";
        t.web.evaluateJavascript(js, value -> {
            try {
                Object o = new JSONTokener(value).nextValue();
                JSONObject j = new JSONObject(String.valueOf(o));
                String body = j.optString("h", "");
                if (body.isEmpty()) { Toast.makeText(this, "Nothing to show in reader mode", Toast.LENGTH_SHORT).show(); return; }
                String bg = darkMode ? "#202124" : "#faf7f0";
                String fg = darkMode ? "#e8eaed" : "#222";
                String page = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>"
                        + "body{max-width:42em;margin:0 auto;padding:20px;font-family:Georgia,serif;line-height:1.7;font-size:18px;background:" + bg + ";color:" + fg + "}"
                        + "h1,h2,h3{font-family:sans-serif;line-height:1.3}</style></head><body><h1>"
                        + android.text.TextUtils.htmlEncode(j.optString("t", "")) + "</h1>" + body + "</body></html>";
                t.web.loadDataWithBaseURL(NEWTAB_BASE + "reader", page, "text/html", "utf-8", null);
            } catch (Exception e) {
                Toast.makeText(this, "Reader mode is not available on this page", Toast.LENGTH_SHORT).show();
            }
        });
    }

    /** Long press on a link or an image. */
    private boolean onLongPress(final Tab tab) {
        WebView.HitTestResult r = tab.web.getHitTestResult();
        if (r == null) return false;
        final String extra = r.getExtra();
        if (extra == null) return false;
        int type = r.getType();
        final ArrayList<String> labels = new ArrayList<>();
        final ArrayList<Runnable> acts = new ArrayList<>();
        if (type == WebView.HitTestResult.SRC_ANCHOR_TYPE) {
            labels.add("Open in new tab"); acts.add(() -> newTab(extra, false, true));
            labels.add("Open in private tab"); acts.add(() -> newTab(extra, true, true));
            labels.add("Copy link"); acts.add(() -> copyText(extra));
            labels.add("Share link"); acts.add(() -> {
                Intent i = new Intent(Intent.ACTION_SEND);
                i.setType("text/plain");
                i.putExtra(Intent.EXTRA_TEXT, extra);
                startActivity(Intent.createChooser(i, "Share link"));
            });
        } else if (type == WebView.HitTestResult.IMAGE_TYPE || type == WebView.HitTestResult.SRC_IMAGE_ANCHOR_TYPE) {
            labels.add("Open image in new tab"); acts.add(() -> newTab(extra, false, true));
            labels.add("Download image"); acts.add(() -> startDownload(extra, tab.mobileUa, null, null));
            labels.add("Copy image address"); acts.add(() -> copyText(extra));
        } else {
            return false;
        }
        new AlertDialog.Builder(this).setTitle(extra.length() > 60 ? extra.substring(0, 60) + "\u2026" : extra)
                .setItems(labels.toArray(new String[0]), (d, which) -> acts.get(which).run()).show();
        return true;
    }

    // ───────────────────────────── permissions: camera, microphone, location ─────────────────────────────
    private String permKey(String origin, String kind) {
        return "perm:" + origin + ":" + kind;
    }

    private void handleWebPermission(final Tab tab, final PermissionRequest request) {
        final String origin = request.getOrigin() == null ? "this site" : request.getOrigin().toString();
        ArrayList<String> allowed = new ArrayList<>();
        ArrayList<String> androidPerms = new ArrayList<>();
        boolean cam = false, mic = false;
        for (String res : request.getResources()) {
            if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(res)) { cam = true; allowed.add(res); androidPerms.add(android.Manifest.permission.CAMERA); }
            else if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(res)) { mic = true; allowed.add(res); androidPerms.add(android.Manifest.permission.RECORD_AUDIO); }
            // anything else (protected media id, MIDI) is refused
        }
        if (allowed.isEmpty()) { request.deny(); return; }
        final String kind = (cam ? "camera" : "") + (cam && mic ? "+" : "") + (mic ? "microphone" : "");
        final String[] res = allowed.toArray(new String[0]);
        final String[] perms = androidPerms.toArray(new String[0]);
        String saved = tab.priv ? "" : prefs.getString(permKey(origin, kind), "");
        if (saved.equals("deny")) { request.deny(); return; }
        if (saved.equals("allow")) { grantWithAndroidPermission(request, res, perms); return; }
        askSitePermission("Allow " + origin + " to use your " + kind.replace("+", " and ") + "?", !tab.priv, new SiteAnswer() {
            @Override public void answer(boolean allow, boolean remember) {
                if (remember) prefs.edit().putString(permKey(origin, kind), allow ? "allow" : "deny").apply();
                if (allow) grantWithAndroidPermission(request, res, perms); else request.deny();
            }
        });
    }

    private void grantWithAndroidPermission(PermissionRequest request, String[] res, String[] perms) {
        ArrayList<String> missing = new ArrayList<>();
        for (String pm : perms) if (checkSelfPermission(pm) != PackageManager.PERMISSION_GRANTED) missing.add(pm);
        if (missing.isEmpty()) { request.grant(res); return; }
        if (pendingPerm != null) { request.deny(); return; }
        pendingPerm = request;
        pendingResources = res;
        requestPermissions(missing.toArray(new String[0]), REQ_MEDIA);
    }

    private void handleGeoPermission(final Tab tab, final String origin, final GeolocationPermissions.Callback callback) {
        runOnUiThread(() -> {
            String saved = tab.priv ? "" : prefs.getString(permKey(origin, "location"), "");
            if (saved.equals("deny")) { callback.invoke(origin, false, false); return; }
            if (saved.equals("allow")) { grantGeo(origin, callback); return; }
            askSitePermission("Allow " + origin + " to know your location?", !tab.priv, new SiteAnswer() {
                @Override public void answer(boolean allow, boolean remember) {
                    if (remember) prefs.edit().putString(permKey(origin, "location"), allow ? "allow" : "deny").apply();
                    if (allow) grantGeo(origin, callback); else callback.invoke(origin, false, false);
                }
            });
        });
    }

    private void grantGeo(String origin, GeolocationPermissions.Callback callback) {
        if (checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            callback.invoke(origin, true, false);
            return;
        }
        if (pendingGeoCb != null) { callback.invoke(origin, false, false); return; }
        pendingGeoCb = callback;
        pendingGeoOrigin = origin;
        requestPermissions(new String[]{android.Manifest.permission.ACCESS_FINE_LOCATION, android.Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_GEO);
    }

    private interface SiteAnswer { void answer(boolean allow, boolean remember); }

    private void askSitePermission(String question, boolean canRemember, final SiteAnswer a) {
        final boolean[] remember = {false};
        AlertDialog.Builder b = new AlertDialog.Builder(this).setTitle(question).setCancelable(false);
        if (canRemember) {
            b.setMultiChoiceItems(new String[]{"Remember my choice for this site"}, remember,
                    (d, which, checked) -> remember[0] = checked);
        }
        b.setPositiveButton("Allow", (d, w) -> a.answer(true, remember[0]));
        b.setNegativeButton("Block", (d, w) -> a.answer(false, remember[0]));
        b.show();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        boolean ok = grantResults.length > 0;
        for (int r : grantResults) if (r != PackageManager.PERMISSION_GRANTED) ok = false;
        if (requestCode == REQ_MEDIA && pendingPerm != null) {
            if (ok) pendingPerm.grant(pendingResources); else pendingPerm.deny();
            pendingPerm = null; pendingResources = null;
        } else if (requestCode == REQ_GEO && pendingGeoCb != null) {
            boolean any = false;
            for (int r : grantResults) if (r == PackageManager.PERMISSION_GRANTED) any = true;
            pendingGeoCb.invoke(pendingGeoOrigin, any, false);
            pendingGeoCb = null; pendingGeoOrigin = null;
        }
    }

    private void resetSitePermissions() {
        SharedPreferences.Editor e = prefs.edit();
        for (String k : new ArrayList<>(prefs.getAll().keySet())) if (k.startsWith("perm:")) e.remove(k);
        e.apply();
        Toast.makeText(this, "Saved site permissions were reset", Toast.LENGTH_SHORT).show();
    }

    // ───────────────────────────── voice search ─────────────────────────────
    private void voiceSearch() {
        try {
            Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
            i.putExtra(RecognizerIntent.EXTRA_PROMPT, "Say what you want to search for");
            startActivityForResult(i, REQ_VOICE);
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "Voice search is not available on this phone", Toast.LENGTH_LONG).show();
        }
    }

    // ───────────────────────────── download manager ─────────────────────────────
    private void rememberDownload(long id, String name) {
        try {
            JSONArray a = new JSONArray(prefs.getString("downloads", "[]"));
            JSONObject o = new JSONObject();
            o.put("id", id);
            o.put("n", name);
            a.put(o);
            JSONArray trimmed = new JSONArray();
            for (int i = Math.max(0, a.length() - 100); i < a.length(); i++) trimmed.put(a.get(i));
            prefs.edit().putString("downloads", trimmed.toString()).apply();
        } catch (Exception ignored) { }
    }

    private void showDownloads() {
        final DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        final ArrayList<Long> ids = new ArrayList<>();
        final ArrayList<String> labels = new ArrayList<>();
        final ArrayList<Boolean> done = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(prefs.getString("downloads", "[]"));
            for (int i = a.length() - 1; i >= 0; i--) {                    // newest first
                JSONObject o = a.getJSONObject(i);
                long id = o.getLong("id");
                String status = "removed";
                boolean ok = false;
                Cursor c = dm.query(new DownloadManager.Query().setFilterById(id));
                if (c != null) {
                    try {
                        if (c.moveToFirst()) {
                            int st = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
                            long total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
                            long got = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
                            if (st == DownloadManager.STATUS_SUCCESSFUL) { status = "done"; ok = true; }
                            else if (st == DownloadManager.STATUS_FAILED) status = "failed";
                            else if (st == DownloadManager.STATUS_PAUSED) status = "paused";
                            else status = total > 0 ? (got * 100 / total) + "%" : "downloading";
                        }
                    } finally { c.close(); }
                }
                ids.add(id); done.add(ok);
                labels.add(o.optString("n", "file") + "  \u2014  " + status);
            }
        } catch (Exception ignored) { }
        if (ids.isEmpty()) { Toast.makeText(this, "No downloads yet", Toast.LENGTH_SHORT).show(); return; }
        new AlertDialog.Builder(this).setTitle("Downloads")
                .setItems(labels.toArray(new String[0]), (d, which) -> downloadActions(dm, ids.get(which), done.get(which)))
                .setNeutralButton("Open Downloads app", (d, w) -> startActivity(new Intent(DownloadManager.ACTION_VIEW_DOWNLOADS)))
                .setNegativeButton("Close", null).show();
    }

    private void downloadActions(final DownloadManager dm, final long id, final boolean finished) {
        final ArrayList<String> labels = new ArrayList<>();
        final ArrayList<Runnable> acts = new ArrayList<>();
        if (finished) {
            labels.add("Open"); acts.add(() -> {
                try {
                    Uri u = dm.getUriForDownloadedFile(id);
                    Intent i = new Intent(Intent.ACTION_VIEW);
                    i.setDataAndType(u, dm.getMimeTypeForDownloadedFile(id));
                    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(i);
                } catch (Exception e) {
                    Toast.makeText(this, "No app can open this file", Toast.LENGTH_SHORT).show();
                }
            });
        }
        labels.add("Delete (file too)"); acts.add(() -> { dm.remove(id); Toast.makeText(this, "Deleted", Toast.LENGTH_SHORT).show(); });
        new AlertDialog.Builder(this).setItems(labels.toArray(new String[0]), (d, which) -> acts.get(which).run()).show();
    }

    // ───────────────────────────── settings ─────────────────────────────
    private void showSettings() {
        final String[] names = {
                "Block ads & trackers",
                "Allow third-party cookies",
                "JavaScript",
                "Safe Browsing (warn about dangerous sites)",
                "Save browsing history",
                "Block screenshots (always)",
                "Clear all data when the app closes",
                "Request desktop sites by default",
                "Force dark pages"};
        final boolean[] on = {adBlock, thirdPartyCookies, jsEnabled, safeBrowsing, saveHistory, blockShots, clearOnExit, desktopDefault, darkMode};
        new AlertDialog.Builder(this).setTitle("Settings")
                .setMultiChoiceItems(names, on, (d, which, checked) -> on[which] = checked)
                .setPositiveButton("Save", (d, w) -> {
                    adBlock = on[0]; thirdPartyCookies = on[1]; jsEnabled = on[2]; safeBrowsing = on[3]; saveHistory = on[4];
                    blockShots = on[5]; clearOnExit = on[6]; desktopDefault = on[7]; darkMode = on[8];
                    prefs.edit().putBoolean("adblock", adBlock).putBoolean("thirdcookies", thirdPartyCookies).putBoolean("js", jsEnabled)
                            .putBoolean("safebrowsing", safeBrowsing).putBoolean("savehistory", saveHistory).putBoolean("blockshots", blockShots)
                            .putBoolean("clearonexit", clearOnExit).putBoolean("desktopdefault", desktopDefault).putBoolean("dark", darkMode).apply();
                    for (Tab t : tabs) applyTabSettings(t);
                    applySecure();
                    if (current != null) current.web.reload();
                    Toast.makeText(this, "Settings saved", Toast.LENGTH_SHORT).show();
                })
                .setNeutralButton("More\u2026", (d, w) -> showMoreSettings())
                .setNegativeButton("Cancel", null).show();
    }

    private void showMoreSettings() {
        final ArrayList<String> labels = new ArrayList<>();
        final ArrayList<Runnable> acts = new ArrayList<>();
        labels.add("Search engine: " + ENGINE_NAMES[engine]); acts.add(this::chooseEngine);
        labels.add("Text size: " + TEXT_SIZES[textSizeIndex] + "%"); acts.add(this::cycleTextSize);
        labels.add("Home page: " + (homeUrl.isEmpty() ? "new tab page" : homeUrl)); acts.add(this::chooseHome);
        labels.add("Reset saved site permissions"); acts.add(this::resetSitePermissions);
        labels.add("Clear browsing data"); acts.add(this::clearData);
        new AlertDialog.Builder(this).setTitle("More settings")
                .setItems(labels.toArray(new String[0]), (d, which) -> acts.get(which).run())
                .setNegativeButton("Close", null).show();
    }

    private void chooseHome() {
        final EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setHint("https://example.com  (empty = new tab page)");
        input.setText(homeUrl);
        new AlertDialog.Builder(this).setTitle("Home page for new tabs").setView(input)
                .setPositiveButton("Save", (d, w) -> {
                    String t = input.getText().toString().trim();
                    if (!t.isEmpty() && !t.startsWith("https://")) t = t.startsWith("http://") ? "https://" + t.substring(7) : "https://" + t;
                    homeUrl = t;
                    prefs.edit().putString("home", homeUrl).apply();
                })
                .setNegativeButton("Cancel", null).show();
    }

    private void clearAllDataNow() {
        CookieManager.getInstance().removeAllCookies(null);
        CookieManager.getInstance().flush();
        WebStorage.getInstance().deleteAllData();
        prefs.edit().putString("history", "[]").putString("session", "[]").apply();
        for (Tab t : tabs) { t.web.clearCache(true); t.web.clearHistory(); t.web.clearFormData(); }
    }

    // ───────────────────────────── printing ─────────────────────────────
    /** Whole page: Android's own print window (preview, paper size, orientation, colour, copies, page range, Save as PDF). */
    private void printPage() {
        try {
            PrintManager pm = (PrintManager) getSystemService(Context.PRINT_SERVICE);
            String name = current.title == null || current.title.isEmpty() ? "SPS page" : current.title;
            boolean us = "US".equals(Locale.getDefault().getCountry()) || "CA".equals(Locale.getDefault().getCountry());
            PrintAttributes attrs = new PrintAttributes.Builder()
                    .setMediaSize(us ? PrintAttributes.MediaSize.NA_LETTER : PrintAttributes.MediaSize.ISO_A4)
                    .setMinMargins(PrintAttributes.Margins.NO_MARGINS).build();
            pm.print(name, current.web.createPrintDocumentAdapter(name), attrs);
        } catch (Exception e) {
            Toast.makeText(this, "Printing is not available", Toast.LENGTH_SHORT).show();
        }
    }

    /** Selected area: drag a box on the page; only that part is printed (as a picture). */
    private void printSelectedArea() {
        final Tab t = current;
        if (t == null) return;
        Toast.makeText(this, "Drag a box around the part to print", Toast.LENGTH_LONG).show();
        final SelectionView sel = new SelectionView(this);
        webHolder.addView(sel, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        sel.listener = rect -> {
            webHolder.removeView(sel);
            if (rect == null) return;
            try {
                Bitmap full = Bitmap.createBitmap(t.web.getWidth(), t.web.getHeight(), Bitmap.Config.ARGB_8888);
                android.graphics.Canvas c = new android.graphics.Canvas(full);
                c.drawColor(Color.WHITE);
                t.web.draw(c);
                int l = Math.max(0, rect.left), tp = Math.max(0, rect.top);
                int w = Math.min(full.getWidth() - l, rect.width()), h = Math.min(full.getHeight() - tp, rect.height());
                if (w < 10 || h < 10) return;
                Bitmap crop = Bitmap.createBitmap(full, l, tp, w, h);
                PrintManager pm = (PrintManager) getSystemService(Context.PRINT_SERVICE);
                pm.print("SPS selection", new BitmapPrintAdapter(this, crop), new PrintAttributes.Builder().build());
            } catch (Throwable e) {
                Toast.makeText(this, "Could not print the selected area", Toast.LENGTH_SHORT).show();
            }
        };
    }

    /** Transparent layer that lets the user drag a rectangle. */
    private static class SelectionView extends View {
        interface Listener { void done(android.graphics.Rect r); }
        Listener listener;
        private float x0, y0, x1, y1;
        private boolean dragging;
        private final android.graphics.Paint dim = new android.graphics.Paint();
        private final android.graphics.Paint line = new android.graphics.Paint();

        SelectionView(Context c) {
            super(c);
            dim.setColor(Color.argb(110, 0, 0, 0));
            line.setColor(Color.parseColor("#1A73E8"));
            line.setStyle(android.graphics.Paint.Style.STROKE);
            line.setStrokeWidth(5f);
        }

        @Override
        protected void onDraw(android.graphics.Canvas c) {
            c.drawRect(0, 0, getWidth(), getHeight(), dim);
            if (dragging || (x1 != x0 && y1 != y0)) {
                float l = Math.min(x0, x1), t = Math.min(y0, y1), r = Math.max(x0, x1), b = Math.max(y0, y1);
                c.save();
                c.clipRect(l, t, r, b);
                c.drawColor(Color.TRANSPARENT, android.graphics.PorterDuff.Mode.CLEAR);
                c.restore();
                c.drawRect(l, t, r, b, line);
            }
        }

        @Override
        public boolean onTouchEvent(android.view.MotionEvent e) {
            switch (e.getAction()) {
                case android.view.MotionEvent.ACTION_DOWN: x0 = x1 = e.getX(); y0 = y1 = e.getY(); dragging = true; invalidate(); return true;
                case android.view.MotionEvent.ACTION_MOVE: x1 = e.getX(); y1 = e.getY(); invalidate(); return true;
                case android.view.MotionEvent.ACTION_UP:
                    x1 = e.getX(); y1 = e.getY(); dragging = false;
                    if (listener != null) listener.done(new android.graphics.Rect((int) Math.min(x0, x1), (int) Math.min(y0, y1), (int) Math.max(x0, x1), (int) Math.max(y0, y1)));
                    return true;
                case android.view.MotionEvent.ACTION_CANCEL: if (listener != null) listener.done(null); return true;
                default: return super.onTouchEvent(e);
            }
        }
    }

    /** Prints one bitmap, scaled to fit the chosen paper. */
    private static class BitmapPrintAdapter extends android.print.PrintDocumentAdapter {
        private final Context ctx;
        private final Bitmap bmp;
        private PrintAttributes attrs;

        BitmapPrintAdapter(Context c, Bitmap b) { ctx = c; bmp = b; }

        @Override
        public void onLayout(PrintAttributes oldA, PrintAttributes newA, android.os.CancellationSignal cs,
                             LayoutResultCallback cb, Bundle extras) {
            attrs = newA;
            if (cs.isCanceled()) { cb.onLayoutCancelled(); return; }
            cb.onLayoutFinished(new android.print.PrintDocumentInfo.Builder("selection.pdf")
                    .setContentType(android.print.PrintDocumentInfo.CONTENT_TYPE_DOCUMENT).setPageCount(1).build(), true);
        }

        @Override
        public void onWrite(android.print.PageRange[] pages, android.os.ParcelFileDescriptor dest, android.os.CancellationSignal cs,
                            WriteResultCallback cb) {
            android.print.pdf.PrintedPdfDocument doc = new android.print.pdf.PrintedPdfDocument(ctx, attrs);
            try {
                android.graphics.pdf.PdfDocument.Page page = doc.startPage(0);
                android.graphics.Canvas c = page.getCanvas();
                float w = c.getWidth(), h = c.getHeight();
                float s = Math.min(w / bmp.getWidth(), h / bmp.getHeight());
                android.graphics.RectF dst = new android.graphics.RectF(0, 0, bmp.getWidth() * s, bmp.getHeight() * s);
                c.drawBitmap(bmp, null, dst, null);
                doc.finishPage(page);
                doc.writeTo(new java.io.FileOutputStream(dest.getFileDescriptor()));
                cb.onWriteFinished(new android.print.PageRange[]{android.print.PageRange.ALL_PAGES});
            } catch (Exception e) {
                cb.onWriteFailed(e.toString());
            } finally {
                doc.close();
            }
        }
    }

    private void toggleDesktop() {
        current.desktop = !current.desktop;
        WebSettings s = current.web.getSettings();
        s.setUserAgentString(current.desktop ? DESKTOP_UA : current.mobileUa);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        current.web.reload();
        Toast.makeText(this, current.desktop ? "Desktop site" : "Mobile site", Toast.LENGTH_SHORT).show();
    }

    private void sharePage() {
        if (isNewTab(current.url)) return;
        Intent i = new Intent(Intent.ACTION_SEND);
        i.setType("text/plain");
        i.putExtra(Intent.EXTRA_TEXT, current.url);
        startActivity(Intent.createChooser(i, "Share link"));
    }

    private void showAbout() {
        String v = "";
        try { v = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Exception ignored) { }
        new AlertDialog.Builder(this).setTitle("SPS Browser " + v)
                .setMessage("A private browser for Android.\n\n"
                        + "• No analytics, no tracking, no account\n"
                        + "• Pages load over https only\n"
                        + "• Ad and tracker blocking, private tabs, bookmarks, history\n"
                        + "• Everything is stored on this phone only\n\n"
                        + "Private tabs do not save history or use the cache; cookies are shared with normal tabs until you choose "
                        + "\"Clear browsing data\".")
                .setPositiveButton("OK", null).show();
    }

    private void clearData() {
        new AlertDialog.Builder(this).setTitle("Clear browsing data?")
                .setMessage("Deletes history, cookies, site data and the cache. Bookmarks are kept.")
                .setPositiveButton("Clear", (d, w) -> {
                    clearAllDataNow();
                    Toast.makeText(this, "Browsing data cleared", Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("Cancel", null).show();
    }

    // ───────────────────────────── bookmarks and history ─────────────────────────────
    private boolean isBookmarked(String url) {
        try {
            JSONArray b = new JSONArray(prefs.getString("bookmarks", "[]"));
            for (int i = 0; i < b.length(); i++) if (b.getJSONObject(i).getString("u").equals(url)) return true;
        } catch (Exception ignored) { }
        return false;
    }

    private void toggleBookmark() {
        if (isNewTab(current.url)) { Toast.makeText(this, "Open a page first", Toast.LENGTH_SHORT).show(); return; }
        try {
            JSONArray b = new JSONArray(prefs.getString("bookmarks", "[]"));
            JSONArray out = new JSONArray();
            boolean removed = false;
            for (int i = 0; i < b.length(); i++) {
                JSONObject o = b.getJSONObject(i);
                if (o.getString("u").equals(current.url)) removed = true; else out.put(o);
            }
            if (!removed) {
                JSONObject o = new JSONObject();
                o.put("t", current.title);
                o.put("u", current.url);
                out.put(o);
            }
            prefs.edit().putString("bookmarks", out.toString()).apply();
            Toast.makeText(this, removed ? "Bookmark removed" : "Bookmarked", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "Could not save the bookmark", Toast.LENGTH_SHORT).show();
        }
    }

    private void showBookmarks() {
        try {
            final JSONArray b = new JSONArray(prefs.getString("bookmarks", "[]"));
            if (b.length() == 0) { Toast.makeText(this, "No bookmarks yet", Toast.LENGTH_SHORT).show(); return; }
            String[] names = new String[b.length()];
            for (int i = 0; i < names.length; i++) names[i] = b.getJSONObject(i).optString("t", b.getJSONObject(i).getString("u"));
            new AlertDialog.Builder(this).setTitle("Bookmarks")
                    .setItems(names, (d, which) -> {
                        try { current.web.loadUrl(b.getJSONObject(which).getString("u")); } catch (Exception ignored) { }
                    })
                    .setNegativeButton("Close", null).show();
        } catch (Exception ignored) { }
    }

    private void addHistory(String title, String url) {
        try {
            JSONArray h = new JSONArray(prefs.getString("history", "[]"));
            if (h.length() > 0 && h.getJSONObject(h.length() - 1).getString("u").equals(url)) return;   // same page twice in a row
            JSONObject o = new JSONObject();
            o.put("t", title == null ? url : title);
            o.put("u", url);
            h.put(o);
            JSONArray trimmed = new JSONArray();
            for (int i = Math.max(0, h.length() - 300); i < h.length(); i++) trimmed.put(h.get(i));   // keep the last 300
            prefs.edit().putString("history", trimmed.toString()).apply();
        } catch (Exception ignored) { }
    }

    private void showHistory() {
        try {
            final JSONArray h = new JSONArray(prefs.getString("history", "[]"));
            if (h.length() == 0) { Toast.makeText(this, "History is empty", Toast.LENGTH_SHORT).show(); return; }
            final int n = h.length();
            String[] names = new String[n];
            for (int i = 0; i < n; i++) {                       // newest first
                JSONObject o = h.getJSONObject(n - 1 - i);
                names[i] = o.optString("t", o.getString("u"));
            }
            new AlertDialog.Builder(this).setTitle("History")
                    .setItems(names, (d, which) -> {
                        try { current.web.loadUrl(h.getJSONObject(n - 1 - which).getString("u")); } catch (Exception ignored) { }
                    })
                    .setNeutralButton("Clear history", (d, w) -> prefs.edit().putString("history", "[]").apply())
                    .setNegativeButton("Close", null).show();
        } catch (Exception ignored) { }
    }

    // ───────────────────────────── find in page ─────────────────────────────
    private void openFindBar() {
        findBar.setVisibility(View.VISIBLE);
        findInput.requestFocus();
        InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
        if (imm != null) imm.showSoftInput(findInput, 0);
    }

    private void closeFindBar() {
        if (findBar == null || findBar.getVisibility() != View.VISIBLE) return;
        findBar.setVisibility(View.GONE);
        findInput.setText("");
        if (current != null) current.web.clearMatches();
        hideKeyboard();
    }

    // ───────────────────────────── ad / tracker blocking ─────────────────────────────
    private void loadBlocklist() {
        try (BufferedReader r = new BufferedReader(new InputStreamReader(getAssets().open("blocklist.txt"), "UTF-8"))) {
            String line;
            while ((line = r.readLine()) != null) {
                line = line.trim().toLowerCase();
                if (!line.isEmpty() && !line.startsWith("#")) blocked.add(line);
            }
        } catch (Exception ignored) { }
    }

    private boolean isBlockedHost(String host) {
        if (host == null) return false;
        String h = host.toLowerCase();
        while (h != null && h.indexOf('.') > 0) {
            if (blocked.contains(h)) return true;
            h = h.substring(h.indexOf('.') + 1);
        }
        return false;
    }

    // ───────────────────────────── helpers ─────────────────────────────
    private Button barButton(String label) {
        Button b = new Button(this);
        b.setText(label);
        b.setAllCaps(false);
        b.setMinWidth(0);
        b.setMinimumWidth(dp(40));
        b.setPadding(dp(6), 0, dp(6), 0);
        b.setBackgroundColor(Color.TRANSPARENT);
        return b;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void hideKeyboard() {
        InputMethodManager imm = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
        View f = getCurrentFocus();
        if (imm != null && f != null) imm.hideSoftInputFromWindow(f.getWindowToken(), 0);
        urlBar.clearFocus();
    }

    // ───────────────────────────── life cycle ─────────────────────────────
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == FILE_CHOOSER && filePathCallback != null) {
            filePathCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            filePathCallback = null;
            return;
        }
        if (requestCode == REQ_VOICE && resultCode == RESULT_OK && data != null) {
            ArrayList<String> r = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (r != null && !r.isEmpty()) go(r.get(0));
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        Uri data = intent.getData();
        if (data != null) newTab(data.toString(), false, true);
    }

    @Override
    public void onBackPressed() {
        if (customView != null) {
            hideCustomViewNow();
        } else if (findBar.getVisibility() == View.VISIBLE) {
            closeFindBar();
        } else if (current != null && current.web.canGoBack()) {
            current.web.goBack();
        } else if (tabs.size() > 1 && current != null) {
            closeTab(current);
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        try {                                                   // remember the open (non-private) tabs
            JSONArray saved = new JSONArray();
            int index = 0;
            for (Tab t : tabs) {
                if (t.priv) continue;
                if (t == current) index = saved.length();
                saved.put(isNewTab(t.url) ? "" : t.url);
            }
            prefs.edit().putString("session", saved.toString()).putInt("session_index", index).apply();
        } catch (Exception ignored) { }
        for (Tab t : tabs) t.web.onPause();
        CookieManager.getInstance().flush();
    }

    @Override
    protected void onResume() {
        super.onResume();
        for (Tab t : tabs) t.web.onResume();
    }

    @Override
    protected void onDestroy() {
        if (clearOnExit && isFinishing()) clearAllDataNow();
        for (Tab t : new ArrayList<>(tabs)) {
            webHolder.removeView(t.web);
            t.web.destroy();
        }
        tabs.clear();
        super.onDestroy();
    }
}
