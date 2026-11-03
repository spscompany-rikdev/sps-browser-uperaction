package com.spscompany.spsbrowser;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.app.KeyguardManager;
import android.app.Dialog;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Switch;
import android.widget.ScrollView;
import org.json.JSONException;
import java.util.List;
import java.util.Date;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.DialogInterface;
import android.content.pm.PackageManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
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
public class MainActivity extends Activity implements Host {

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

    private final ArrayList<BTab> tabs = new ArrayList<>();
    private BTab current;
    private final Set<String> blocked = new HashSet<>();
    private final AtomicInteger blockedCount = new AtomicInteger(0);

    private SharedPreferences prefs;
    private boolean adBlock = true;
    private boolean hideBanners = true;              // hides cookie / consent pop-ups of the common consent tools
    private boolean ytShield = true;                  // YouTube: remove the ads from the player data (like Brave), no lag
    private String ytJs;
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

    private Profiles profiles;
    private Store store;
    private final ArrayList<View> pages = new ArrayList<>();
    private final ArrayList<String[]> recentlyClosed = new ArrayList<>();
    private LinearLayout bottomBar, pill, bannerSlot;
    private TextView tabsCountText, profileAvatar;
    private ImageView lockIcon, starIcon, reloadIcon, backIcon, fwdIcon;
    private boolean offerSave = true, offerFill = true, requireUnlock = true, switchingProfile;
    private long unlockedAt, lastSaveOffer;
    private Runnable pendingUnlock;
    private final Set<String> neverSave = new HashSet<>();
    private final Handler ui = new Handler(Looper.getMainLooper());
    private static final int REQ_AUTH = 4713;
    private static final int REQ_APPLOCK = 4714;
    private static final int REQ_LENS = 4716, REQ_LENS_PERM = 4717;
    private Uri lensCamera;
    private static final int REQ_CAMERA_PERM = 4715;
    private boolean stripLinks = true, appLock = false, askDownload = false, dailyQuote = true;
    private int quoteIndex;
    private boolean autoUpdate = true;
    private long downloadingUpdate = -1;
    private final Set<String> extOn = new HashSet<>(), extSiteOff = new HashSet<>();
    private JSONArray userScripts = new JSONArray();
    private boolean noAutoplay, noPopups, keepAwake;
    private final Set<String> shieldOff = new HashSet<>();
    private long blockedTotal, blockedSaved, leftAt;
    private View lockOverlay;
    private boolean lockPending;
    private Uri cameraOutput;

    private FrameLayout root;
    private FrameLayout webHolder;
    private LinearLayout bar;
    private LinearLayout findBar;
    private EditText urlBar;
    private EditText findInput;
    private ProgressBar progress;
    private View customView;
    private WebChromeClient.CustomViewCallback customViewCallback;
    private ValueCallback<Uri[]> filePathCallback;

    // ───────────────────────────── start ─────────────────────────────
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Ico.load(this);
        profiles = new Profiles(this);
        profiles.applyWebViewData();                       // must happen before the first WebView exists
        prefs = getSharedPreferences(profiles.prefsName(profiles.activeId()), MODE_PRIVATE);
        store = new Store(prefs, profiles.activeId());
        adBlock = prefs.getBoolean("adblock", true);
        ytShield = prefs.getBoolean("ytshield", true);
        hideBanners = prefs.getBoolean("hidebanners", true);
        darkMode = prefs.getBoolean("dark", false);
        thirdPartyCookies = prefs.getBoolean("thirdcookies", false);
        jsEnabled = prefs.getBoolean("js", true);
        safeBrowsing = prefs.getBoolean("safebrowsing", true);
        saveHistory = prefs.getBoolean("savehistory", true);
        blockShots = prefs.getBoolean("blockshots", false);
        clearOnExit = prefs.getBoolean("clearonexit", false);
        desktopDefault = prefs.getBoolean("desktopdefault", false);
        offerSave = prefs.getBoolean("offersave", true);
        offerFill = prefs.getBoolean("offerfill", true);
        requireUnlock = prefs.getBoolean("requireunlock", true);
        stripLinks = prefs.getBoolean("striplinks", true);
        appLock = prefs.getBoolean("applock", false);
        askDownload = prefs.getBoolean("askdownload", false);
        dailyQuote = prefs.getBoolean("dailyquote", true);
        autoUpdate = prefs.getBoolean("autoupdate", true);
        extOn.addAll(prefs.getStringSet("ext_on", new HashSet<String>()));
        extSiteOff.addAll(prefs.getStringSet("ext_siteoff", new HashSet<String>()));
        try { userScripts = new JSONArray(prefs.getString("ext_user", "[]")); } catch (Exception e) { userScripts = new JSONArray(); }
        noAutoplay = prefs.getBoolean("noautoplay", false);
        noPopups = prefs.getBoolean("nopopups", true);
        keepAwake = prefs.getBoolean("keepawake", false);
        blockedTotal = prefs.getLong("blocked_total", 0);
        shieldOff.addAll(prefs.getStringSet("shieldoff", new HashSet<String>()));
        lockPending = appLock;
        applyKeepAwake();
        neverSave.addAll(prefs.getStringSet("neversave", new HashSet<String>()));
        homeUrl = prefs.getString("home", "");
        engine = Math.max(0, Math.min(ENGINE_URLS.length - 1, prefs.getInt("engine", 0)));
        textSizeIndex = Math.max(0, Math.min(TEXT_SIZES.length - 1, prefs.getInt("textsize", 0)));
        loadBlocklist();
        buildUi();
        applySystemBars();

        boolean any = false;
        try {
            JSONArray saved = new JSONArray(prefs.getString("session", "[]"));
            for (int i = 0; i < saved.length(); i++) {
                Object e = saved.get(i);
                String u = e instanceof JSONObject ? ((JSONObject) e).optString("u") : String.valueOf(e);
                BTab t = newTab(u, false, false);
                if (e instanceof JSONObject) t.pinned = ((JSONObject) e).optBoolean("p");
                any = true;
            }
        } catch (Exception ignored) { }
        Uri data = getIntent() != null ? getIntent().getData() : null;
        if (data != null) newTab(data.toString(), false, true);
        else if (!any) newTab(null, false, true);
        else switchTo(tabs.get(Math.min(prefs.getInt("session_index", 0), tabs.size() - 1)));
        final Intent first = getIntent();
        if (first != null && first.getStringExtra(SearchWidget.CMD) != null) ui.postDelayed(() -> handleCommand(first), 400);
    }

    private void buildUi() {
        root = new FrameLayout(this);
        root.setBackgroundColor(UI.BG);

        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);

        // ── top toolbar: profile | address pill | reload ──
        bar = new LinearLayout(this);
        bar.setOrientation(LinearLayout.HORIZONTAL);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setBackgroundColor(UI.BG);
        bar.setPadding(dp(10), dp(6), dp(6), dp(6));

        Profiles.Profile ap = profiles.active();
        profileAvatar = UI.avatar(this, ap.name, ap.color, 34);
        profileAvatar.setOnClickListener(v -> showProfiles());
        bar.addView(profileAvatar);
        bar.addView(UI.space(this, 8, 1));

        pill = new LinearLayout(this);
        pill.setOrientation(LinearLayout.HORIZONTAL);
        pill.setGravity(Gravity.CENTER_VERTICAL);
        pill.setBackground(UI.box(this, UI.SURFACE, 22, UI.BORDER));
        pill.setPadding(dp(12), 0, dp(2), 0);
        lockIcon = new ImageView(this);
        lockIcon.setImageDrawable(Ico.of("search", UI.TEXT3));
        lockIcon.setOnClickListener(v -> showShield());
        pill.addView(lockIcon, new LinearLayout.LayoutParams(dp(18), dp(18)));
        urlBar = new EditText(this);
        urlBar.setSingleLine(true);
        urlBar.setTextSize(15);
        urlBar.setTextColor(UI.TEXT);
        urlBar.setHintTextColor(UI.TEXT3);
        urlBar.setHint("Search or type a web address");
        urlBar.setImeOptions(EditorInfo.IME_ACTION_GO);
        urlBar.setInputType(android.text.InputType.TYPE_TEXT_VARIATION_URI);
        urlBar.setSelectAllOnFocus(true);
        urlBar.setBackground(null);
        urlBar.setPadding(dp(10), 0, dp(6), 0);
        pill.addView(urlBar, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f));
        starIcon = UI.icon(this, "star", UI.TEXT2, 38, 9);
        starIcon.setOnClickListener(v -> toggleBookmark());
        pill.addView(starIcon);
        ImageView micIcon = UI.icon(this, "mic", UI.TEXT2, 38, 9);
        micIcon.setOnClickListener(v -> voiceSearch());
        pill.addView(micIcon);
        ImageView lensIcon = UI.icon(this, "image", UI.TEXT2, 38, 9);
        lensIcon.setOnClickListener(v -> startLens());
        pill.addView(lensIcon);
        bar.addView(pill, new LinearLayout.LayoutParams(0, dp(44), 1f));
        reloadIcon = UI.icon(this, "reload", UI.TEXT, 44, 11);
        reloadIcon.setOnClickListener(v -> {
            if (current == null) return;
            if (current.loading) current.web.stopLoading(); else current.web.reload();
        });
        bar.addView(reloadIcon);
        urlBar.setOnFocusChangeListener((v, focus) -> {
            boolean pv = current != null && current.priv;
            pill.setBackground(focus ? UI.box(this, UI.BG, 22, pv ? UI.PRIVATE : UI.ACCENT) : UI.box(this, pv ? UI.PRIVATE_BG : UI.SURFACE, 22, UI.BORDER));
        });

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        progress.setProgressTintList(android.content.res.ColorStateList.valueOf(UI.ACCENT));
        progress.setVisibility(View.GONE);

        // ── find in page ──
        findBar = new LinearLayout(this);
        findBar.setOrientation(LinearLayout.HORIZONTAL);
        findBar.setGravity(Gravity.CENTER_VERTICAL);
        findBar.setBackgroundColor(UI.BG);
        findBar.setPadding(dp(10), dp(6), dp(4), dp(6));
        findBar.setVisibility(View.GONE);
        findInput = UI.field(this, "Find in page", false);
        ImageView prev = UI.icon(this, "up", UI.TEXT, 40, 9);
        ImageView next = UI.icon(this, "down", UI.TEXT, 40, 9);
        ImageView closeFind = UI.icon(this, "close", UI.TEXT, 40, 9);
        findBar.addView(findInput, new LinearLayout.LayoutParams(0, dp(40), 1f));
        findBar.addView(prev);
        findBar.addView(next);
        findBar.addView(closeFind);

        webHolder = new FrameLayout(this);
        bannerSlot = new LinearLayout(this);
        bannerSlot.setOrientation(LinearLayout.VERTICAL);
        bannerSlot.setPadding(dp(10), dp(6), dp(10), dp(8));
        bannerSlot.setBackgroundColor(UI.BG);
        bannerSlot.setVisibility(View.GONE);

        // ── bottom bar: back | forward | new tab | tabs | menu ──
        bottomBar = new LinearLayout(this);
        bottomBar.setOrientation(LinearLayout.HORIZONTAL);
        bottomBar.setGravity(Gravity.CENTER_VERTICAL);
        bottomBar.setBackgroundColor(UI.BG);
        backIcon = UI.icon(this, "back", UI.TEXT, 48, 12);
        fwdIcon = UI.icon(this, "forward", UI.TEXT, 48, 12);
        ImageView plus = UI.icon(this, "plus", UI.TEXT, 48, 12);
        ImageView menuIcon = UI.icon(this, "menu", UI.TEXT, 48, 12);
        FrameLayout tabsBtn = new FrameLayout(this);
        tabsBtn.setBackground(UI.ripple(this, Color.TRANSPARENT, 24, 0));
        tabsBtn.setClickable(true);
        tabsCountText = UI.text(this, "1", 12, UI.TEXT, true);
        tabsCountText.setGravity(Gravity.CENTER);
        tabsCountText.setBackground(UI.box(this, Color.TRANSPARENT, 6, UI.TEXT));
        tabsBtn.addView(tabsCountText, new FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER));
        for (View v : new View[]{backIcon, fwdIcon, plus, tabsBtn, menuIcon}) {
            bottomBar.addView(v, new LinearLayout.LayoutParams(0, dp(52), 1f));
        }
        backIcon.setOnClickListener(v -> { if (current != null && current.web.canGoBack()) current.web.goBack(); else if (current != null && tabs.size() > 1) closeTab(current); });
        fwdIcon.setOnClickListener(v -> { if (current != null && current.web.canGoForward()) current.web.goForward(); });
        plus.setOnClickListener(v -> newTab(null, current != null && current.priv, true));
        tabsBtn.setOnClickListener(v -> showTabs());
        menuIcon.setOnClickListener(v -> showMenu());

        column.addView(bar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        column.addView(progress, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(2)));
        column.addView(findBar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        column.addView(webHolder, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        column.addView(bannerSlot, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        column.addView(UI.divider(this));
        column.addView(bottomBar, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(column, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);

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
    private BTab newTab(String url, boolean priv, boolean show) {
        BTab t = new BTab();
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

    private void switchTo(BTab t) {
        if (t == null) return;
        if (current != null && current != t) captureThumb(current);
        for (BTab o : tabs) o.web.setVisibility(o == t ? View.VISIBLE : View.GONE);
        current = t;
        t.lastUsed = System.currentTimeMillis();
        urlBar.setText(isNewTab(t.url) ? "" : t.url);
        progress.setVisibility(View.GONE);
        closeFindBar();
        hideBanner();
        applySecure();
        updateTabCount();
        updateChrome();
    }

    /** White status and navigation bars with dark icons (classic look). */
    @SuppressWarnings("deprecation")
    private void applySystemBars() {
        try {
            getWindow().setStatusBarColor(Color.WHITE);
            getWindow().setNavigationBarColor(Color.WHITE);
            int f = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            if (Build.VERSION.SDK_INT >= 26) f |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            getWindow().getDecorView().setSystemUiVisibility(f);
        } catch (Throwable ignored) { }
    }

    /** Small picture of the page for the tab manager (never for private tabs). */
    private void captureThumb(BTab t) {
        if (t == null || t.priv || t.web == null || t.web.getWidth() <= 0 || t.web.getVisibility() != View.VISIBLE) return;
        try {
            int w = t.web.getWidth();
            int h = Math.min(t.web.getHeight(), w * 4 / 3);
            float sc = 420f / w;
            Bitmap b = Bitmap.createBitmap(420, Math.max(1, (int) (h * sc)), Bitmap.Config.RGB_565);
            android.graphics.Canvas cv = new android.graphics.Canvas(b);
            cv.drawColor(Color.WHITE);
            cv.scale(sc, sc);
            t.web.draw(cv);
            t.thumb = b;
        } catch (Throwable ignored) { }
    }

    /** Address-bar icons, back/forward state and private-tab colours. */
    private void updateChrome() {
        if (current == null || urlBar == null) return;
        boolean nt = isNewTab(current.url);
        boolean https = current.url != null && current.url.startsWith("https://");
        UI.setIcon(lockIcon, current.priv ? "incognito" : nt ? "search" : https ? "lock" : "unlock",
                current.priv ? UI.PRIVATE : nt ? UI.TEXT3 : https ? UI.OK : UI.DANGER);
        boolean bm = !nt && store.isBookmarked(current.url);
        UI.setIcon(starIcon, bm ? "starfill" : "star", bm ? UI.ACCENT : UI.TEXT2);
        starIcon.setVisibility(nt ? View.GONE : View.VISIBLE);
        if (!urlBar.hasFocus()) pill.setBackground(UI.box(this, current.priv ? UI.PRIVATE_BG : UI.SURFACE, 22, UI.BORDER));
        boolean cb = current.web.canGoBack() || tabs.size() > 1;
        UI.setIcon(backIcon, "back", cb ? UI.TEXT : UI.TEXT3);
        UI.setIcon(fwdIcon, "forward", current.web.canGoForward() ? UI.TEXT : UI.TEXT3);
        UI.setIcon(reloadIcon, current.loading ? "close" : "reload", UI.TEXT);
    }

    /** Private tabs (and the "Block screenshots" setting) switch on FLAG_SECURE: no screenshots, hidden in the app switcher. */
    private void applyKeepAwake() {
        if (keepAwake) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private void applySecure() {
        boolean secureOpen = false;
        for (View p : pages) if ("secure".equals(p.getTag())) secureOpen = true;
        boolean on = blockShots || secureOpen || (current != null && current.priv);
        if (on) getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
    }

    private void applyTabSettings(BTab t) {
        WebSettings ws = t.web.getSettings();
        ws.setJavaScriptEnabled(jsEnabled);
        if (Build.VERSION.SDK_INT >= 26) ws.setSafeBrowsingEnabled(safeBrowsing);
        CookieManager.getInstance().setAcceptThirdPartyCookies(t.web, thirdPartyCookies);
        ws.setTextZoom(TEXT_SIZES[textSizeIndex]);
        ws.setMediaPlaybackRequiresUserGesture(noAutoplay);
        ws.setSupportMultipleWindows(!noPopups);
        applyDark(ws);
    }

    private void closeTab(BTab t) {
        int i = tabs.indexOf(t);
        if (i < 0) return;
        if (!t.priv && t.url != null && t.url.startsWith("http")) {
            recentlyClosed.add(new String[]{t.title, t.url});
            if (recentlyClosed.size() > 25) recentlyClosed.remove(0);
        }
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
        updateChrome();
    }

    private void updateTabCount() {
        if (tabsCountText != null) tabsCountText.setText(tabs.size() > 99 ? ":)" : String.valueOf(tabs.size()));
    }

    private final TabsPage.Ops tabOps = new TabsPage.Ops() {
        @Override public List<BTab> tabs() { return tabs; }
        @Override public BTab current() { return current; }
        @Override public void switchTo(BTab t) { MainActivity.this.switchTo(t); }
        @Override public void close(BTab t) { closeTab(t); }
        @Override public BTab newTab(String url, boolean priv) { return MainActivity.this.newTab(url, priv, url == null); }
        @Override public void captureThumb(BTab t) { MainActivity.this.captureThumb(t); }
        @Override public void sortByTitle() {
            java.util.Collections.sort(tabs, (a, b) -> a.title.compareToIgnoreCase(b.title));
        }
        @Override public List<String[]> recentlyClosed() { return recentlyClosed; }
        @Override public void reopen(String[] e) { MainActivity.this.newTab(e[1], false, true); recentlyClosed.remove(e); }
    };

    private void showTabs() {
        hideKeyboard();
        push(new TabsPage(this, tabOps));
    }

    // ───────────────────────────── web view ─────────────────────────────
    private void setupWebView(final BTab tab) {
        final WebView web = tab.web;
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true);          // needed so files and photos picked for upload can be read
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
                if (stripLinks && request.isForMainFrame() && (scheme.equals("https") || scheme.equals("http"))
                        && !shieldOff.contains(UI.hostOf(u.toString()))) {
                    String cleaned = Shield.stripTracking(u.toString());
                    if (!cleaned.equals(u.toString())) { view.loadUrl(cleaned.startsWith("http://") ? "https://" + cleaned.substring(7) : cleaned); return true; }
                }
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
                String reqHost = request.getUrl().getHost();
                String pageHost = UI.hostOf(tab.url);
                if (adBlock && ytShield && !request.isForMainFrame() && isYoutubeAdRequest(request.getUrl()) && !shieldOff.contains(pageHost)) {
                    blockedCount.incrementAndGet();
                    return new WebResourceResponse("text/plain", "utf-8", new ByteArrayInputStream(new byte[0]));
                }
                if (adBlock && !request.isForMainFrame() && !shieldOff.contains(pageHost) && isBlockedHost(reqHost)
                        && Shield.isThirdParty(pageHost, reqHost)) {
                    blockedCount.incrementAndGet();
                    return new WebResourceResponse("text/plain", "utf-8", new ByteArrayInputStream(new byte[0]));
                }
                return null;
            }

            @Override
            public void onPageCommitVisible(WebView view, String url) {
                injectYoutubeShield(view, url);
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                injectYoutubeShield(view, url);
                tab.url = url == null ? "" : url;
                tab.loading = true;
                if (tab == current) {
                    updateChrome();
                    progress.setVisibility(View.VISIBLE);
                    if (!urlBar.hasFocus()) urlBar.setText(isNewTab(tab.url) ? "" : tab.url);
                }
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                tab.url = url == null ? "" : url;
                tab.loading = false;
                String title = view.getTitle();
                if (title != null && !title.isEmpty()) tab.title = title;
                if (tab == current) {
                    progress.setVisibility(View.GONE);
                    if (!urlBar.hasFocus()) urlBar.setText(isNewTab(tab.url) ? "" : tab.url);
                }
                if (!tab.priv && saveHistory && !isNewTab(tab.url) && tab.url.startsWith("https://")) addHistory(tab.title, tab.url);
                injectYoutubeShield(view, url);
                afterPageLoad(tab, view);
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
                bottomBar.setVisibility(View.GONE);
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
                launchFileChooser(params, true);
                return true;
            }
        });

        web.addJavascriptInterface(new AutofillBridge(tab), "SPSAF");
        web.setOnLongClickListener(v -> onLongPress(tab));

        web.setDownloadListener((url, userAgent, contentDisposition, mimetype, contentLength) -> {
            if (!askDownload) { startDownload(url, userAgent, contentDisposition, mimetype); return; }
            String name = URLUtil.guessFileName(url, contentDisposition, mimetype);
            String size = contentLength > 0 ? "  (" + android.text.format.Formatter.formatShortFileSize(MainActivity.this, contentLength) + ")" : "";
            new AlertDialog.Builder(MainActivity.this).setTitle("Download file?").setMessage(name + size + "\nfrom " + UI.hostOf(url))
                    .setPositiveButton("Download", (d, w) -> startDownload(url, userAgent, contentDisposition, mimetype))
                    .setNegativeButton("Cancel", null).show();
        });
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
                store.addDownload(id, name, url);
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
        bottomBar.setVisibility(View.VISIBLE);
        applySystemBars();
        if (customViewCallback != null) customViewCallback.onCustomViewHidden();
    }

    @SuppressWarnings("deprecation")
    private void applyDark(WebSettings s) {
        if (Build.VERSION.SDK_INT >= 29) {
            try { s.setForceDark(darkMode ? WebSettings.FORCE_DARK_ON : WebSettings.FORCE_DARK_OFF); } catch (Throwable ignored) { }
        }
    }

    // ───────────────────────────── new-tab page ─────────────────────────────
    private void loadNewTabPage(BTab t) {
        StringBuilder sites = new StringBuilder();
        String[][] quick = {
                {"Google", "https://www.google.com/"}, {"YouTube", "https://www.youtube.com/"},
                {"Wikipedia", "https://www.wikipedia.org/"}, {"GitHub", "https://github.com/"}};
        for (String[] q : quick) sites.append(tile(q[0], q[1]));
        int n = 0;
        for (JSONObject o : store.bookmarks()) {
            if (n++ >= 12) break;
            sites.append(tile(o.optString("t", o.optString("u")), o.optString("u")));
        }
        String[] qt = Quotes.at(Quotes.today());
        boolean dk = darkMode && !t.priv;
        String bg = t.priv ? "#F3EEFB" : (dk ? "#17181B" : "#F4F6FB");
        String card = t.priv ? "#FFFFFF" : (dk ? "#24262B" : "#FFFFFF");
        String fg = t.priv ? "#3B2A63" : (dk ? "#E8EAED" : "#202124");
        String sub = dk ? "#9AA0A6" : "#6B7280";
        String hero = t.priv ? "linear-gradient(135deg,#6D4AFF,#B07CFF)" : "linear-gradient(135deg,#1A73E8,#5BA7FF)";
        String page = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>"
                + "body{font-family:sans-serif;margin:0;padding:18px 16px 36px;background:" + bg + ";color:" + fg + "}"
                + ".w{max-width:560px;margin:0 auto}"
                + ".h{border-radius:26px;padding:26px 22px 24px;background:" + hero + ";color:#fff;box-shadow:0 8px 24px rgba(26,115,232,.28)}"
                + ".h h1{font-weight:600;font-size:26px;margin:0 0 4px}.h p{margin:0 0 18px;font-size:13px;opacity:.9}"
                + "input{width:100%;box-sizing:border-box;padding:14px 20px;border-radius:26px;border:none;background:#fff;color:#202124;font-size:16px;outline:none}"
                + ".c{margin-top:16px;border-radius:22px;padding:16px 14px 10px;background:" + card + ";box-shadow:0 2px 10px rgba(0,0,0,.07)}"
                + ".c h2{margin:0 0 8px 6px;font-size:13px;font-weight:600;letter-spacing:.6px;text-transform:uppercase;color:" + sub + "}"
                + ".g{display:flex;flex-wrap:wrap}"
                + ".s{width:25%;box-sizing:border-box;padding:6px 2px;text-align:center;text-decoration:none;color:inherit;font-size:12px}"
                + ".s i{display:flex;align-items:center;justify-content:center;width:50px;height:50px;margin:0 auto 6px;border-radius:18px;background:#E8F0FE;color:#1A73E8;font-style:normal;font-weight:700;font-size:20px}"
                + ".s b{display:block;font-weight:400;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
                + ".q{position:relative;padding:20px 22px 18px}.q:before{content:'\\201C';position:absolute;left:14px;top:-4px;font-size:64px;color:#1A73E8;opacity:.25;font-family:serif}"
                + ".q p{margin:6px 0 10px;font-size:16px;line-height:1.5;font-style:italic}.q span{font-size:13px;color:" + sub + ";font-weight:600}"
                + "</style></head><body><div class='w'><div class='h'><h1>SPS Browser</h1><p>" + (t.priv ? "Private tab \u2014 no history is saved" : "Fast, private browsing") + "</p>"
                + "<form action='" + ENGINE_URLS[engine] + "' method='get'><input name='q' placeholder='Search " + ENGINE_NAMES[engine] + " or type a web address' autocomplete='off'></form></div>"
                + "<div class='c'><h2>Shortcuts</h2><div class='g'>" + sites + "</div></div>"
                + "<div class='c q'><h2>Thought of the day</h2><p>" + android.text.TextUtils.htmlEncode(qt[0]) + "</p><span>\u2014 " + android.text.TextUtils.htmlEncode(qt[1]) + "</span></div>"
                + "</div></body></html>";
        t.url = NEWTAB_BASE;
        t.title = t.priv ? "New private tab" : "New tab";
        t.web.loadDataWithBaseURL(NEWTAB_BASE, page, "text/html", "utf-8", null);
    }

    private static String tile(String title, String url) {
        String t = title == null || title.isEmpty() ? url : title;
        String letter = android.text.TextUtils.htmlEncode(t.substring(0, 1).toUpperCase());
        return "<a class='s' href='" + android.text.TextUtils.htmlEncode(url) + "'><i>" + letter + "</i><b>" + android.text.TextUtils.htmlEncode(t) + "</b></a>";
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
        for (BTab t : tabs) t.web.getSettings().setTextZoom(TEXT_SIZES[textSizeIndex]);
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
        final BTab t = current;
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
    private boolean onLongPress(final BTab tab) {
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
            labels.add("Search this image with Lens"); acts.add(() -> newTab(Lens.byUrl(extra), false, true));
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

    private void handleWebPermission(final BTab tab, final PermissionRequest request) {
        final String origin = request.getOrigin() == null ? "this site" : request.getOrigin().toString();
        ArrayList<String> allowed = new ArrayList<>();
        ArrayList<String> androidPerms = new ArrayList<>();
        boolean cam = false, mic = false, drm = false, midi = false;
        for (String res : request.getResources()) {
            if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(res)) { cam = true; allowed.add(res); androidPerms.add(android.Manifest.permission.CAMERA); }
            else if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(res)) { mic = true; allowed.add(res); androidPerms.add(android.Manifest.permission.RECORD_AUDIO); }
            else if (PermissionRequest.RESOURCE_PROTECTED_MEDIA_ID.equals(res)) { drm = true; allowed.add(res); }
            else if (PermissionRequest.RESOURCE_MIDI_SYSEX.equals(res)) { midi = true; allowed.add(res); }
        }
        if (allowed.isEmpty()) { request.deny(); return; }
        ArrayList<String> kinds = new ArrayList<>();
        if (cam) kinds.add("camera"); if (mic) kinds.add("microphone"); if (drm) kinds.add("protected content (DRM)"); if (midi) kinds.add("MIDI devices");
        final String kind = android.text.TextUtils.join("+", kinds);
        final String[] res = allowed.toArray(new String[0]);
        final String[] perms = androidPerms.toArray(new String[0]);
        String saved = tab.priv ? "" : prefs.getString(permKey(origin, kind), "");
        if (saved.equals("deny")) { request.deny(); return; }
        if (saved.equals("allow")) { grantWithAndroidPermission(request, res, perms); return; }
        askSitePermission("Allow " + origin + " to use " + (cam || mic ? "your " : "") + kind.replace("+", " and ") + "?", !tab.priv, new SiteAnswer() {
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

    private void handleGeoPermission(final BTab tab, final String origin, final GeolocationPermissions.Callback callback) {
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
        if (requestCode == REQ_LENS_PERM) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) lensCapture();
            else toast("Camera permission is needed to search with the camera");
            return;
        }
        if (requestCode == REQ_CAMERA_PERM) {
            String k = pendingKind;
            pendingKind = null;
            boolean ok = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
            if (k != null && ok && filePathCallback != null) pickSource(k);
            else { finishFileChooser(null); toast("Camera permission is needed to take a photo or video"); }
            return;
        }
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
    // ───────────────────────────── settings ─────────────────────────────
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

    /** Selected area: drag a box on the page; only that part is printed (as a picture). Never crashes: every step is guarded. */
    private void printSelectedArea() {
        final BTab t = current;
        if (t == null || t.web == null) return;
        Toast.makeText(this, "Drag a box around the part to print", Toast.LENGTH_LONG).show();
        final SelectionView sel = new SelectionView(this);
        webHolder.addView(sel, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        sel.listener = rect -> {
            // never change the view tree from inside its own touch callback (that was the crash): do it on the next loop
            webHolder.post(() -> {
                try { webHolder.removeView(sel); } catch (Throwable ignored) { }
                if (rect == null) return;
                captureArea(t.web, rect, bmp -> {
                    if (bmp == null) { Toast.makeText(this, "Could not capture that part of the page", Toast.LENGTH_SHORT).show(); return; }
                    areaActions(bmp);
                });
            });
        };
    }

    private interface BitmapCb { void got(Bitmap b); }

    /** PixelCopy (reads what is really on screen, works with the hardware-accelerated WebView); View.draw only as a fallback. */
    private void captureArea(final View v, android.graphics.Rect r, final BitmapCb cb) {
        try {
            final int[] loc = new int[2];
            v.getLocationInWindow(loc);
            int l = Math.max(0, r.left), tp = Math.max(0, r.top);
            int w = Math.min(v.getWidth() - l, r.width()), h = Math.min(v.getHeight() - tp, r.height());
            if (w < 12 || h < 12) { cb.got(null); return; }
            // keep memory sane: very big boxes are captured at most 4000 px wide/high
            if (w > 4000 || h > 4000) { cb.got(null); return; }
            final Bitmap out = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
            final android.graphics.Rect src = new android.graphics.Rect(loc[0] + l, loc[1] + tp, loc[0] + l + w, loc[1] + tp + h);
            if (android.os.Build.VERSION.SDK_INT >= 26) {
                android.view.PixelCopy.request(getWindow(), src, out, res -> {
                    cb.got(res == android.view.PixelCopy.SUCCESS ? out : null);
                }, new android.os.Handler(android.os.Looper.getMainLooper()));
                return;
            }
            android.graphics.Canvas c = new android.graphics.Canvas(out);
            c.drawColor(Color.WHITE);
            c.translate(-l, -tp);
            v.draw(c);
            cb.got(out);
        } catch (Throwable e) {
            cb.got(null);
        }
    }

    private void areaActions(final Bitmap bmp) {
        final String[] items = {"Print / Save as PDF", "Save as picture (Pictures folder)", "Share picture"};
        new AlertDialog.Builder(this).setTitle("Selected area").setItems(items, (d, which) -> {
            try {
                if (which == 0) {
                    PrintManager pm = (PrintManager) getSystemService(Context.PRINT_SERVICE);
                    pm.print("SPS selection", new BitmapPrintAdapter(this, bmp), new PrintAttributes.Builder().build());
                } else {
                    android.net.Uri u = saveBitmapToPictures(bmp);
                    if (u == null) { Toast.makeText(this, "Could not save the picture", Toast.LENGTH_SHORT).show(); return; }
                    if (which == 1) Toast.makeText(this, "Saved in Pictures/SPS", Toast.LENGTH_SHORT).show();
                    else {
                        Intent i = new Intent(Intent.ACTION_SEND).setType("image/png").putExtra(Intent.EXTRA_STREAM, u)
                                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        startActivity(Intent.createChooser(i, "Share picture"));
                    }
                }
            } catch (Throwable e) {
                Toast.makeText(this, "That did not work: " + e.getClass().getSimpleName(), Toast.LENGTH_SHORT).show();
            }
        }).setNegativeButton("Cancel", null).show();
    }

    private android.net.Uri saveBitmapToPictures(Bitmap bmp) {
        try {
            android.content.ContentValues cv = new android.content.ContentValues();
            cv.put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, "SPS_" + System.currentTimeMillis() + ".png");
            cv.put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/png");
            if (android.os.Build.VERSION.SDK_INT >= 29) cv.put(android.provider.MediaStore.Images.Media.RELATIVE_PATH, "Pictures/SPS");
            android.net.Uri u = getContentResolver().insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, cv);
            if (u == null) return null;
            try (java.io.OutputStream os = getContentResolver().openOutputStream(u)) { bmp.compress(Bitmap.CompressFormat.PNG, 100, os); }
            return u;
        } catch (Throwable e) { return null; }
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
                        + "\u2022 No analytics, no tracking, no account\n"
                        + "\u2022 Pages load over https only\n"
                        + "\u2022 Ad and tracker blocking, private tabs, tab manager\n"
                        + "\u2022 Profiles with separate bookmarks, history, passwords and logins\n"
                        + "\u2022 Passwords, autofill info, bookmarks and history are encrypted with a key that never leaves this phone\n"
                        + "\u2022 Everything is stored on this phone only\n\n"
                        + "Private tabs do not save history or use the cache; cookies are shared with normal tabs of the same profile until you choose "
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

    private static boolean isYoutubeHost(String h) {
        return h != null && (h.equals("youtube.com") || h.endsWith(".youtube.com"));
    }

    /** Only the requests that load or report ads - never the video or the page itself, so nothing can break or lag. */
    private boolean isYoutubeAdRequest(android.net.Uri u) {
        String h = u.getHost(), p = u.getPath();
        if (h == null || p == null) return false;
        h = h.toLowerCase();
        if (h.equals("googleads.g.doubleclick.net") || h.equals("static.doubleclick.net") || h.endsWith(".googlesyndication.com")) return true;
        if (!isYoutubeHost(h)) return false;
        return p.startsWith("/api/stats/ads") || p.startsWith("/pagead/") || p.startsWith("/ptracking") || p.startsWith("/get_midroll_info")
                || p.startsWith("/api/stats/atr") && u.toString().contains("adformat");
    }

    /** The script is idempotent (it guards itself), so it may be injected on several page events. */
    private static final String BANNER_JS = "(function(){if(document.getElementById('sps-banner-css'))return;var s=document.createElement('style');s.id='sps-banner-css';"
            + "s.textContent='#onetrust-banner-sdk,#onetrust-consent-sdk,#CybotCookiebotDialog,#cookie-law-info-bar,#cmpbox,.cc-window,.cookie-notice,#cookie-notice,"
            + ".truste_overlay,.truste_box_overlay,#sp_message_container_0,.fc-consent-root,#didomi-host,.qc-cmp2-container,#usercentrics-root,"
            + ".osano-cm-window,#cookiebanner,.cookie-banner,.cookie-consent{display:none !important} html,body{overflow:auto !important}';"
            + "(document.head||document.documentElement).appendChild(s);})();";

    private void injectYoutubeShield(WebView view, String url) {
        try {
            if (hideBanners && url != null && url.startsWith("http") && !UI.hostOf(url).isEmpty() && !shieldOff.contains(UI.hostOf(url)))
                view.evaluateJavascript(BANNER_JS, null);
            if (!adBlock || !ytShield || url == null) return;
            String host = UI.hostOf(url);
            if (!isYoutubeHost(host) || shieldOff.contains(host)) return;
            if (ytJs == null) {
                try (java.io.InputStream in = getAssets().open("yt_shield.js")) {
                    java.io.ByteArrayOutputStream bo = new java.io.ByteArrayOutputStream();
                    byte[] buf = new byte[4096]; int n;
                    while ((n = in.read(buf)) > 0) bo.write(buf, 0, n);
                    ytJs = bo.toString("UTF-8");
                }
            }
            view.evaluateJavascript(ytJs, null);
        } catch (Throwable ignored) { }
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


    // ───────────────────────────── file and photo upload ─────────────────────────────
    private static String[] acceptTypes(WebChromeClient.FileChooserParams p) {
        ArrayList<String> out = new ArrayList<>();
        String[] a = p.getAcceptTypes();
        if (a != null) for (String t : a) {
            if (t == null) continue;
            for (String one : t.split(",")) {
                one = one.trim().toLowerCase(Locale.ROOT);
                if (one.isEmpty()) continue;
                if (one.startsWith(".")) {                                   // ".pdf" -> application/pdf
                    String m = android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(one.substring(1));
                    one = m == null ? "*/*" : m;
                }
                if (!out.contains(one)) out.add(one);
            }
        }
        if (out.isEmpty()) out.add("*/*");
        return out.toArray(new String[0]);
    }

    private String pendingKind;

    /** Asks WHERE the file should come from (files, photos, videos, camera ...) - like other browsers - then opens that picker. */
    private void launchFileChooser(final WebChromeClient.FileChooserParams params, boolean unused) {
        final String[] types = acceptTypes(params);
        boolean any = false, img = false, vid = false;
        for (String t : types) { if (t.equals("*/*")) any = true; if (t.startsWith("image/")) img = true; if (t.startsWith("video/")) vid = true; }
        final boolean multi = params.getMode() == WebChromeClient.FileChooserParams.MODE_OPEN_MULTIPLE;
        final boolean wantImg = any || img, wantVid = any || vid;
        chooserTypes = types; chooserMulti = multi;
        if (params.isCaptureEnabled() && (img || vid)) { pickSource(img ? "photo" : "video"); return; }
        final ArrayList<String> labels = new ArrayList<>(), kinds = new ArrayList<>();
        labels.add("Files"); kinds.add("files");
        if (wantImg) { labels.add("Photos & gallery"); kinds.add("photos"); }
        if (wantVid && !wantImg) { labels.add("Videos"); kinds.add("videos"); }
        if (wantImg) { labels.add("Take a photo"); kinds.add("photo"); }
        if (wantVid) { labels.add("Record a video"); kinds.add("video"); }
        String site = current == null ? "" : UI.hostOf(current.url);
        new AlertDialog.Builder(this).setTitle(site.isEmpty() ? "Choose a file to upload" : site + " asks for a file")
                .setItems(labels.toArray(new String[0]), (d, which) -> pickSource(kinds.get(which)))
                .setOnCancelListener(d -> finishFileChooser(null))
                .setNegativeButton("Cancel", (d, w) -> finishFileChooser(null)).show();
    }

    private String[] chooserTypes = {"*/*"};
    private boolean chooserMulti;

    private void pickSource(String kind) {
        cameraOutput = null;
        Intent it;
        if (kind.equals("photo") || kind.equals("video")) {
            if (checkSelfPermission(android.Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                pendingKind = kind;
                requestPermissions(new String[]{android.Manifest.permission.CAMERA}, REQ_CAMERA_PERM);
                return;
            }
            if (kind.equals("photo")) {
                try {
                    android.content.ContentValues cv = new android.content.ContentValues();
                    cv.put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, "SPS_" + System.currentTimeMillis() + ".jpg");
                    cv.put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                    Uri out = getContentResolver().insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, cv);
                    if (out == null) throw new IllegalStateException("no output");
                    cameraOutput = out;
                    it = new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
                    it.putExtra(android.provider.MediaStore.EXTRA_OUTPUT, out);
                    it.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
                } catch (Exception e) { finishFileChooser(null); toast("Camera is not available"); return; }
            } else {
                it = new Intent(android.provider.MediaStore.ACTION_VIDEO_CAPTURE);
            }
        } else if (kind.equals("photos") || kind.equals("videos")) {
            it = new Intent(Intent.ACTION_GET_CONTENT);
            it.addCategory(Intent.CATEGORY_OPENABLE);
            it.setType(kind.equals("photos") ? "image/*" : "video/*");
            if (chooserMulti) it.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        } else {                                                        // "files": the real file browser (Downloads, Documents, drives ...)
            it = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            it.addCategory(Intent.CATEGORY_OPENABLE);
            it.setType("*/*");
            if (!(chooserTypes.length == 1 && chooserTypes[0].equals("*/*"))) it.putExtra(Intent.EXTRA_MIME_TYPES, chooserTypes);
            if (chooserMulti) it.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        }
        try {
            startActivityForResult(it, FILE_CHOOSER);
        } catch (Exception e) {
            finishFileChooser(null);
            toast("No app can do that on this phone");
        }
    }

    private void finishFileChooser(Uri[] results) {
        ValueCallback<Uri[]> cb = filePathCallback;
        filePathCallback = null;
        if (cb != null) cb.onReceiveValue(results);
    }

    private void onFileChosen(int resultCode, Intent data) {
        Uri[] results = null;
        Uri cam = cameraOutput;
        cameraOutput = null;
        if (resultCode == RESULT_OK) {
            ArrayList<Uri> list = new ArrayList<>();
            if (data != null) {
                if (data.getClipData() != null) {
                    for (int i = 0; i < data.getClipData().getItemCount(); i++) {
                        Uri u = data.getClipData().getItemAt(i).getUri();
                        if (u != null) list.add(u);
                    }
                } else if (data.getData() != null) {
                    list.add(data.getData());
                }
            }
            if (list.isEmpty() && cam != null) { list.add(cam); cam = null; }       // the camera app was used
            if (!list.isEmpty()) results = list.toArray(new Uri[0]);
        }
        if (cam != null) { try { getContentResolver().delete(cam, null, null); } catch (Exception ignored) { } }   // unused empty photo entry
        finishFileChooser(results);
        if (results == null && resultCode == RESULT_OK) toast("The file could not be read");
    }

    // ───────────────────────────── pages (Host) ─────────────────────────────
    @Override public Activity act() { return this; }
    @Override public Store store() { return store; }

    @Override
    public void open(String url, boolean newTab) {
        if (newTab || current == null) newTab(url, false, true); else current.web.loadUrl(url);
    }

    @Override
    public void push(View page) {
        hideKeyboard();
        pages.add(page);
        root.addView(page, UI.match());
        page.setAlpha(0f);
        page.animate().alpha(1f).setDuration(130).start();
        applySecure();
    }

    @Override
    public void pop() {
        if (pages.isEmpty()) return;
        View top = pages.remove(pages.size() - 1);
        root.removeView(top);
        applySecure();
        updateChrome();
        updateTabCount();
    }

    void refreshTopPage() {
        if (pages.isEmpty()) return;
        View top = pages.get(pages.size() - 1);
        if (top instanceof ListPage) ((ListPage) top).refresh();
    }

    @Override public void toast(String s) { Toast.makeText(this, s, Toast.LENGTH_SHORT).show(); }

    @Override
    public void share(String text) {
        Intent i = new Intent(Intent.ACTION_SEND);
        i.setType("text/plain");
        i.putExtra(Intent.EXTRA_TEXT, text);
        startActivity(Intent.createChooser(i, "Share"));
    }

    @Override
    public void copySecret(String text) {
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm == null) return;
        final ClipData clip = ClipData.newPlainText("SPS", text);
        if (Build.VERSION.SDK_INT >= 33) {
            android.os.PersistableBundle pb = new android.os.PersistableBundle();
            pb.putBoolean("android.content.extra.IS_SENSITIVE", true);       // keyboards / the clipboard preview hide it
            clip.getDescription().setExtras(pb);
        }
        cm.setPrimaryClip(clip);
        toast("Copied - clipboard clears in 30 seconds");
        final ClipboardManager fcm = cm;
        ui.postDelayed(() -> {
            try {
                if (Build.VERSION.SDK_INT >= 28) fcm.clearPrimaryClip(); else fcm.setPrimaryClip(ClipData.newPlainText("", ""));
            } catch (Throwable ignored) { }
        }, 30000);
    }

    /** Asks for the phone's screen lock (PIN, pattern, fingerprint) before saved passwords are used. Valid for 2 minutes. */
    @Override
    @SuppressWarnings("deprecation")
    public void unlock(Runnable ok) {
        long now = System.currentTimeMillis();
        KeyguardManager km = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        if (!requireUnlock || km == null || !km.isDeviceSecure() || now - unlockedAt < 120000) { ok.run(); return; }
        Intent i = km.createConfirmDeviceCredentialIntent("SPS Browser", "Confirm your screen lock to use saved passwords");
        if (i == null) { ok.run(); return; }
        pendingUnlock = ok;
        try {
            startActivityForResult(i, REQ_AUTH);
        } catch (Exception e) {
            pendingUnlock = null;
            toast("Could not ask for the screen lock");
        }
    }

    // ───────────────────────────── main menu ─────────────────────────────
    private View quickAction(final Dialog[] d, String icon, String label, boolean enabled, final Runnable r) {
        LinearLayout b = new LinearLayout(this);
        b.setOrientation(LinearLayout.VERTICAL);
        b.setGravity(Gravity.CENTER);
        b.setPadding(0, dp(10), 0, dp(10));
        ImageView i = new ImageView(this);
        i.setImageDrawable(Ico.of(icon, enabled ? UI.TEXT : UI.TEXT3));
        b.addView(i, new LinearLayout.LayoutParams(dp(24), dp(24)));
        TextView t = UI.text(this, label, 11, enabled ? UI.TEXT2 : UI.TEXT3, false);
        t.setPadding(0, dp(4), 0, 0);
        b.addView(t);
        if (enabled) {
            b.setBackground(UI.ripple(this, Color.TRANSPARENT, 12, 0));
            b.setOnClickListener(v -> { d[0].dismiss(); r.run(); });
        }
        b.setLayoutParams(new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return b;
    }

    private void menuRow(LinearLayout box, final Dialog[] d, String icon, String label, String sub, final Runnable r) {
        LinearLayout row = UI.row(this, icon, label, sub, UI.TEXT2);
        row.setOnClickListener(v -> { d[0].dismiss(); r.run(); });
        box.addView(row);
    }

    private void showMenu() {
        if (current == null) return;
        final boolean page = !isNewTab(current.url);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(0, 0, 0, dp(14));
        final Dialog[] d = new Dialog[1];
        LinearLayout quick = new LinearLayout(this);
        quick.setPadding(dp(8), dp(2), dp(8), dp(2));
        boolean bm = page && store.isBookmarked(current.url);
        quick.addView(quickAction(d, "forward", "Forward", current.web.canGoForward(), () -> current.web.goForward()));
        quick.addView(quickAction(d, bm ? "starfill" : "star", bm ? "Bookmarked" : "Bookmark", page, this::toggleBookmark));
        quick.addView(quickAction(d, "share", "Share", page, this::sharePage));
        quick.addView(quickAction(d, "print", "Print", page, this::printPage));
        quick.addView(quickAction(d, "reload", "Reload", true, () -> current.web.reload()));
        box.addView(quick);
        box.addView(UI.divider(this));
        menuRow(box, d, "plus", "New tab", null, () -> newTab(null, false, true));
        menuRow(box, d, "incognito", "New private tab", null, () -> newTab(null, true, true));
        menuRow(box, d, "user", "Profiles", profiles.active().name, this::showProfiles);
        box.addView(UI.divider(this));
        menuRow(box, d, "star", "Bookmarks", null, this::showBookmarks);
        menuRow(box, d, "history", "History", null, this::showHistory);
        menuRow(box, d, "download", "Downloads", null, this::showDownloads);
        menuRow(box, d, "key", "Passwords", store.isSecure() ? "Encrypted, protected by your screen lock" : "Not available on this phone", () -> Vault.openList(this));
        box.addView(UI.divider(this));
        menuRow(box, d, "find", "Find in page", null, this::openFindBar);
        if (page) {
            menuRow(box, d, "reader", "Reader mode", null, this::readerMode);
            menuRow(box, d, "translate", "Translate page", null, this::translatePage);
            menuRow(box, d, "magic", "Fill form (autofill info)", null, this::fillAddress);
            menuRow(box, d, "print", "Print selected area", "Drag a box around the part to print", this::printSelectedArea);
            menuRow(box, d, "copy", "Copy link", null, this::copyLink);
            menuRow(box, d, "external", "Open in another browser", null, this::openExternal);
            menuRow(box, d, "mic", tts != null && ttsSpeaking ? "Stop reading" : "Read aloud", null, this::readAloud);
            menuRow(box, d, "home", "Add to home screen", null, this::addToHomeScreen);
        }
        menuRow(box, d, current.desktop ? "phone" : "desktop", current.desktop ? "Mobile site" : "Desktop site", null, this::toggleDesktop);
        menuRow(box, d, "dark", "Dark pages", darkMode ? "On" : "Off", () -> {
            darkMode = !darkMode; prefs.edit().putBoolean("dark", darkMode).apply();
            for (BTab t : tabs) applyDark(t.web.getSettings());
            current.web.reload();
        });
        menuRow(box, d, "shield", "Privacy shield", adBlock ? blockedCount.get() + " trackers blocked this session" : "Off", this::showShield);
        menuRow(box, d, "magic", "Extension store", extOn.size() + " added", this::showExtensions);
        menuRow(box, d, "mic", "Voice search", null, this::voiceSearch);
        menuRow(box, d, "image", "Search with Lens", "Camera or a photo", this::startLens);
        menuRow(box, d, "sliders", "Page tools", "Screenshot, source, page info ...", this::showTools);
        menuRow(box, d, "bookmark", "Thought of the day", "Words from great people", () -> showQuote(false));
        box.addView(UI.divider(this));
        menuRow(box, d, "settings", "Settings", null, this::showSettings);
        menuRow(box, d, "trash", "Clear browsing data", null, this::clearData);
        menuRow(box, d, "refresh", "Check for updates", "Version " + myVersion(), () -> checkForUpdate(true));
        menuRow(box, d, "info", "About SPS Browser", null, this::showAbout);
        d[0] = UI.sheet(this, box);
        d[0].show();
    }

    // ───────────────────────────── bookmarks ─────────────────────────────
    private void toggleBookmark() {
        if (current == null || isNewTab(current.url)) { toast("Open a page first"); return; }
        if (store.isBookmarked(current.url)) { store.removeBookmarkUrl(current.url); toast("Bookmark removed"); }
        else { store.addBookmark(current.title, current.url); toast("Bookmarked"); }
        updateChrome();
    }

    private void showBookmarks() {
        ListPage p = new ListPage(this, "Bookmarks", () -> {
            List<ListPage.Item> out = new ArrayList<>();
            List<JSONObject> l = store.bookmarks();
            for (int i = l.size() - 1; i >= 0; i--) {
                JSONObject o = l.get(i);
                ListPage.Item it = new ListPage.Item();
                it.id = o.optString("id");
                it.title = o.optString("t");
                it.sub = o.optString("u");
                it.tag = o;
                out.add(it);
            }
            return out;
        }, it -> { open(it.sub, false); pop(); })
                .empty("No bookmarks yet.\nTap the star in the address bar to add one.", "star")
                .bulk("Open in new tabs", "external", false, sel -> { for (ListPage.Item it : sel) newTab(it.sub, false, false); toast(sel.size() + " tabs opened"); })
                .bulk("Share", "share", false, sel -> {
                    StringBuilder sb = new StringBuilder();
                    for (ListPage.Item it : sel) sb.append(it.title).append("\n").append(it.sub).append("\n\n");
                    share(sb.toString().trim());
                })
                .bulk("Edit", "edit", false, sel -> { if (sel.size() == 1) editBookmark(sel.get(0)); else toast("Select one bookmark to edit"); })
                .bulk("Delete", "trash", true, sel -> {
                    Set<String> ids = new HashSet<>();
                    for (ListPage.Item it : sel) ids.add(it.id);
                    store.removeBookmarks(ids);
                    updateChrome();
                });
        p.menu("Bookmark this page", false, s -> toggleBookmark());
        p.menu("Delete all bookmarks", true, s -> new AlertDialog.Builder(this).setMessage("Delete ALL bookmarks?")
                .setPositiveButton("Delete", (dd, w) -> {
                    Set<String> ids = new HashSet<>();
                    for (JSONObject o : store.bookmarks()) ids.add(o.optString("id"));
                    store.removeBookmarks(ids);
                    refreshTopPage();
                    updateChrome();
                }).setNegativeButton("Cancel", null).show());
        push(p);
    }

    private void editBookmark(final ListPage.Item it) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(8), dp(20), dp(4));
        final EditText name = UI.field(this, "Name", false);
        name.setText(it.title);
        final EditText url = UI.field(this, "Address", false);
        url.setText(it.sub);
        box.addView(name);
        box.addView(UI.space(this, 1, 10));
        box.addView(url);
        new AlertDialog.Builder(this).setTitle("Edit bookmark").setView(box)
                .setPositiveButton("Save", (dd, w) -> {
                    String u = url.getText().toString().trim();
                    if (!u.isEmpty() && !u.startsWith("https://") && !u.startsWith("http://")) u = "https://" + u;
                    store.renameBookmark(it.id, name.getText().toString().trim(), u);
                    refreshTopPage();
                }).setNegativeButton("Cancel", null).show();
    }

    // ───────────────────────────── history ─────────────────────────────
    private void addHistory(String title, String url) {
        store.addHistory(title, url);
    }

    private String dayLabel(long ts) {
        java.util.Calendar a = java.util.Calendar.getInstance(), b = java.util.Calendar.getInstance();
        b.setTimeInMillis(ts);
        int days = (int) ((startOfDay(a) - startOfDay(b)) / 86400000L);
        if (days == 0) return "Today";
        if (days == 1) return "Yesterday";
        return android.text.format.DateFormat.format("EEEE, d MMMM yyyy", ts).toString();
    }

    private static long startOfDay(java.util.Calendar c) {
        java.util.Calendar x = (java.util.Calendar) c.clone();
        x.set(java.util.Calendar.HOUR_OF_DAY, 0); x.set(java.util.Calendar.MINUTE, 0); x.set(java.util.Calendar.SECOND, 0); x.set(java.util.Calendar.MILLISECOND, 0);
        return x.getTimeInMillis();
    }

    private void showHistory() {
        final java.text.DateFormat tf = android.text.format.DateFormat.getTimeFormat(this);
        ListPage p = new ListPage(this, "History", () -> {
            List<ListPage.Item> out = new ArrayList<>();
            List<JSONObject> l = store.history();
            for (int i = l.size() - 1; i >= 0; i--) {
                JSONObject o = l.get(i);
                ListPage.Item it = new ListPage.Item();
                it.id = o.optString("id");
                it.title = o.optString("t");
                it.sub = o.optString("u");
                long ts = o.optLong("ts");
                it.section = dayLabel(ts);
                it.trailing = tf.format(new Date(ts));
                out.add(it);
            }
            return out;
        }, it -> { open(it.sub, false); pop(); })
                .empty("Your browsing history will show here", "history")
                .bulk("Open in new tabs", "external", false, sel -> { for (ListPage.Item it : sel) newTab(it.sub, false, false); toast(sel.size() + " tabs opened"); })
                .bulk("Bookmark", "star", false, sel -> { for (ListPage.Item it : sel) store.addBookmark(it.title, it.sub); toast("Bookmarked"); updateChrome(); })
                .bulk("Delete", "trash", true, sel -> {
                    Set<String> ids = new HashSet<>();
                    for (ListPage.Item it : sel) ids.add(it.id);
                    store.removeHistory(ids);
                });
        p.menu("Clear the last hour", false, s -> clearHistorySince(System.currentTimeMillis() - 3600000L));
        p.menu("Clear today", false, s -> clearHistorySince(startOfDay(java.util.Calendar.getInstance())));
        p.menu("Clear all history", true, s -> new AlertDialog.Builder(this).setMessage("Delete all browsing history?")
                .setPositiveButton("Delete", (dd, w) -> { store.clearHistory(); refreshTopPage(); }).setNegativeButton("Cancel", null).show());
        push(p);
    }

    private void clearHistorySince(long since) {
        Set<String> ids = new HashSet<>();
        for (JSONObject o : store.history()) if (o.optLong("ts") >= since) ids.add(o.optString("id"));
        store.removeHistory(ids);
        toast(ids.size() + " entries deleted");
    }

    // ───────────────────────────── downloads ─────────────────────────────
    private void showDownloads() {
        final DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
        ListPage p = new ListPage(this, "Downloads", () -> downloadItems(dm), it -> {
            Object[] tag = (Object[]) it.tag;
            if ((Boolean) tag[1]) openDownload(dm, (Long) tag[0]); else toast(it.sub);
        })
                .empty("No downloads yet", "download")
                .live(1000)
                .bulk("Share", "share", false, sel -> {
                    if (sel.size() > 1) { toast("Select one file to share"); return; }
                    Object[] tag = (Object[]) sel.get(0).tag;
                    if (!(Boolean) tag[1]) { toast("Not finished yet"); return; }
                    try {
                        Uri u = dm.getUriForDownloadedFile((Long) tag[0]);
                        Intent i = new Intent(Intent.ACTION_SEND);
                        i.setType(dm.getMimeTypeForDownloadedFile((Long) tag[0]));
                        i.putExtra(Intent.EXTRA_STREAM, u);
                        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        startActivity(Intent.createChooser(i, "Share file"));
                    } catch (Exception e) { toast("This file cannot be shared"); }
                })
                .bulk("Remove from list", "close", false, sel -> {
                    Set<String> ids = new HashSet<>();
                    for (ListPage.Item it : sel) ids.add(it.id);
                    store.removeDownloads(ids);
                })
                .bulk("Delete file", "trash", true, sel -> {
                    Set<String> ids = new HashSet<>();
                    for (ListPage.Item it : sel) { ids.add(it.id); dm.remove((Long) ((Object[]) it.tag)[0]); }
                    store.removeDownloads(ids);
                    toast(sel.size() + " deleted");
                });
        p.menu("Open the Downloads app", false, s -> startActivity(new Intent(DownloadManager.ACTION_VIEW_DOWNLOADS)));
        p.menu("Clear the list (keep the files)", false, s -> {
            Set<String> ids = new HashSet<>();
            for (JSONObject o : store.downloads()) ids.add(o.optString("id"));
            store.removeDownloads(ids);
        });
        push(p);
    }

    private List<ListPage.Item> downloadItems(DownloadManager dm) {
        List<ListPage.Item> out = new ArrayList<>();
        List<JSONObject> l = store.downloads();
        if (l.isEmpty()) return out;
        long[] ids = new long[l.size()];
        for (int i = 0; i < ids.length; i++) { try { ids[i] = Long.parseLong(l.get(i).optString("id")); } catch (Exception e) { ids[i] = -1; } }
        java.util.HashMap<Long, long[]> info = new java.util.HashMap<>();      // id -> status, total, got
        Cursor c = null;
        try {
            c = dm.query(new DownloadManager.Query().setFilterById(ids));
            if (c != null) while (c.moveToNext()) {
                long id = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_ID));
                info.put(id, new long[]{c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)),
                        c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES)),
                        c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))});
            }
        } catch (Exception ignored) { } finally { if (c != null) c.close(); }
        final java.text.DateFormat tf = android.text.format.DateFormat.getTimeFormat(this);
        for (int i = l.size() - 1; i >= 0; i--) {
            JSONObject o = l.get(i);
            long id = ids[i];
            long[] f = info.get(id);
            ListPage.Item it = new ListPage.Item();
            it.id = o.optString("id");
            it.title = o.optString("n", "file");
            boolean done = false;
            String status;
            if (f == null) status = "File removed";
            else if (f[0] == DownloadManager.STATUS_SUCCESSFUL) { status = android.text.format.Formatter.formatShortFileSize(this, f[1]); done = true; }
            else if (f[0] == DownloadManager.STATUS_FAILED) status = "Failed";
            else if (f[0] == DownloadManager.STATUS_PAUSED) status = "Paused";
            else {
                it.progress = f[1] > 0 ? (int) (f[2] * 100 / f[1]) : 0;
                status = f[1] > 0 ? it.progress + "%  •  " + android.text.format.Formatter.formatShortFileSize(this, f[2]) + " of " + android.text.format.Formatter.formatShortFileSize(this, f[1]) : "Downloading…";
            }
            String host = UI.hostOf(o.optString("u"));
            it.sub = status + (host.isEmpty() ? "" : "  •  " + host);
            it.trailing = tf.format(new Date(o.optLong("ts")));
            it.warn = f != null && f[0] == DownloadManager.STATUS_FAILED;
            String n = it.title.toLowerCase();
            it.icon = n.matches(".*\\.(png|jpe?g|gif|webp|bmp|heic)$") ? "image" : "file";
            it.color = UI.TEXT2;
            it.section = dayLabel(o.optLong("ts"));
            it.tag = new Object[]{id, done};
            out.add(it);
        }
        return out;
    }

    private void openDownload(DownloadManager dm, long id) {
        try {
            Uri u = dm.getUriForDownloadedFile(id);
            Intent i = new Intent(Intent.ACTION_VIEW);
            i.setDataAndType(u, dm.getMimeTypeForDownloadedFile(id));
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(i);
        } catch (Exception e) {
            toast("No app can open this file");
        }
    }

    private void clearAllDataNow() {
        CookieManager.getInstance().removeAllCookies(null);
        CookieManager.getInstance().flush();
        WebStorage.getInstance().deleteAllData();
        store.clearHistory();
        prefs.edit().putString("session", "[]").apply();
        for (BTab t : tabs) { t.web.clearCache(true); t.web.clearHistory(); t.web.clearFormData(); }
    }

    // ───────────────────────────── settings ─────────────────────────────
    private interface BoolSet { void set(boolean v); }

    private void settingSwitch(LinearLayout parent, String title, String desc, boolean value, final BoolSet set) {
        LinearLayout r = new LinearLayout(this);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(dp(18), dp(12), dp(14), dp(12));
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.addView(UI.text(this, title, 15, UI.TEXT, false));
        if (desc != null) {
            TextView dsc = UI.text(this, desc, 12, UI.TEXT2, false);
            col.addView(dsc);
        }
        r.addView(col, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        final Switch sw = new Switch(this);
        sw.setChecked(value);
        sw.setThumbTintList(android.content.res.ColorStateList.valueOf(value ? UI.ACCENT : 0xFFFFFFFF));
        sw.setOnCheckedChangeListener((b, v) -> {
            sw.setThumbTintList(android.content.res.ColorStateList.valueOf(v ? UI.ACCENT : 0xFFFFFFFF));
            set.set(v);
        });
        r.addView(sw);
        r.setOnClickListener(v -> sw.toggle());
        r.setBackground(UI.ripple(this, Color.TRANSPARENT, 0, 0));
        parent.addView(r);
    }

    private void settingLink(LinearLayout parent, String icon, String title, String sub, final Runnable r) {
        LinearLayout row = UI.row(this, icon, title, sub, UI.TEXT2);
        row.setOnClickListener(v -> r.run());
        parent.addView(row);
    }

    private void settingHeader(LinearLayout parent, String t) {
        TextView h = UI.text(this, t, 13, UI.ACCENT, true);
        h.setPadding(dp(18), dp(20), dp(18), dp(4));
        parent.addView(h);
    }

    private void putBool(String key, boolean v) { prefs.edit().putBoolean(key, v).apply(); }

    private void applyAllTabs() {
        for (BTab t : tabs) applyTabSettings(t);
        applySecure();
    }

    private void showSettings() {
        final LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setBackgroundColor(UI.BG);
        page.setClickable(true);
        page.addView(Vault.topBar(this, "Settings"));
        page.addView(UI.divider(this));
        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setPadding(0, 0, 0, dp(30));

        settingHeader(list, "Privacy & security");
        settingSwitch(list, "Block ads & trackers", "Hides known ad and tracking servers", adBlock, v -> { adBlock = v; putBool("adblock", v); });
        settingSwitch(list, "Smart YouTube ad blocking", "Removes the ad schedule from the video data, hides ad boxes. Light on battery, no lag", ytShield, v -> { ytShield = v; putBool("ytshield", v); });
        settingSwitch(list, "Hide cookie pop-ups", "Hides the consent banners of the common cookie tools (nothing is accepted for you)", hideBanners, v -> { hideBanners = v; putBool("hidebanners", v); });
        settingSwitch(list, "Remove tracking from links", "Cleans utm_*, fbclid, gclid ... from addresses", stripLinks, v -> { stripLinks = v; putBool("striplinks", v); });
        settingSwitch(list, "Allow third-party cookies", "Off is more private; some logins need it", thirdPartyCookies, v -> { thirdPartyCookies = v; putBool("thirdcookies", v); applyAllTabs(); });
        settingSwitch(list, "Safe Browsing", "Warn about dangerous sites", safeBrowsing, v -> { safeBrowsing = v; putBool("safebrowsing", v); applyAllTabs(); });
        settingSwitch(list, "JavaScript", "Turning it off breaks many sites", jsEnabled, v -> { jsEnabled = v; putBool("js", v); applyAllTabs(); });
        settingSwitch(list, "Block screenshots", "Hides the app in the recent-apps list too (always on for private tabs)", blockShots, v -> { blockShots = v; putBool("blockshots", v); applySecure(); });
        settingSwitch(list, "Lock the app with your screen lock", "Ask for PIN, pattern or fingerprint when the app is opened again", appLock, v -> {
            KeyguardManager km = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
            if (v && (km == null || !km.isDeviceSecure())) { toast("Set a screen lock in the phone's Settings first"); appLock = false; putBool("applock", false); return; }
            appLock = v; putBool("applock", v);
        });
        settingSwitch(list, "Save browsing history", null, saveHistory, v -> { saveHistory = v; putBool("savehistory", v); });
        settingSwitch(list, "Clear all data when the app closes", null, clearOnExit, v -> { clearOnExit = v; putBool("clearonexit", v); });

        settingSwitch(list, "Thought of the day", "A short saying from a great person once a day", dailyQuote, v -> { dailyQuote = v; putBool("dailyquote", v); });
        settingLink(list, "lock", "Site permissions", "Reset what sites may use", this::manageSitePermissions);
        settingHeader(list, "Pages");
        settingLink(list, "magic", "Extension store", "Add-ons, your own scripts", this::showExtensions);
        settingSwitch(list, "Block autoplay", "Videos start only when you tap play", noAutoplay, v -> { noAutoplay = v; putBool("noautoplay", v); applyAllTabs(); });
        settingSwitch(list, "Block pop-up windows", "Pages cannot open extra windows by themselves", noPopups, v -> { noPopups = v; putBool("nopopups", v); applyAllTabs(); });
        settingSwitch(list, "Keep screen on while browsing", null, keepAwake, v -> { keepAwake = v; putBool("keepawake", v); applyKeepAwake(); });
        settingHeader(list, "App updates");
        settingSwitch(list, "Check for updates automatically", "At most every 12 hours; nothing is installed without your OK", autoUpdate, v -> { autoUpdate = v; putBool("autoupdate", v); });
        settingLink(list, "refresh", "Check for updates now", "Version " + myVersion(), () -> checkForUpdate(true));
        settingHeader(list, "Downloads");
        settingSwitch(list, "Ask before downloading", "Shows the file name and size first", askDownload, v -> { askDownload = v; putBool("askdownload", v); });
        settingLink(list, "download", "Downloads", "Open the download manager", this::showDownloads);

        settingHeader(list, "Passwords & autofill");
        settingSwitch(list, "Offer to save passwords", "Asks after you sign in. Stored encrypted with a key that never leaves the phone", offerSave, v -> { offerSave = v; putBool("offersave", v); });
        settingSwitch(list, "Offer to fill saved passwords", null, offerFill, v -> { offerFill = v; putBool("offerfill", v); });
        settingSwitch(list, "Ask for screen lock first", "PIN, pattern or fingerprint before passwords are shown or filled", requireUnlock, v -> { requireUnlock = v; putBool("requireunlock", v); });
        settingLink(list, "key", "Password manager", "Saved logins, generator, password check", () -> Vault.openList(this));
        settingLink(list, "magic", "Autofill info", "Name, email, phone, address", () -> Vault.openAutofill(this));
        settingLink(list, "trash", "Sites that never save passwords", neverSave.size() + " sites", this::manageNeverSave);

        settingHeader(list, "Appearance & browsing");
        settingSwitch(list, "Dark pages", "Forces a dark look on websites", darkMode, v -> { darkMode = v; putBool("dark", v); for (BTab t : tabs) applyDark(t.web.getSettings()); });
        settingSwitch(list, "Request desktop sites by default", null, desktopDefault, v -> { desktopDefault = v; putBool("desktopdefault", v); });
        settingLink(list, "search", "Search engine", ENGINE_NAMES[engine], this::chooseEngine);
        settingLink(list, "reader", "Text size", TEXT_SIZES[textSizeIndex] + "%", this::cycleTextSize);
        settingLink(list, "home", "Home page", homeUrl.isEmpty() ? "New tab page" : homeUrl, this::chooseHome);

        settingHeader(list, "Data");
        settingLink(list, "user", "Profiles", "Separate bookmarks, history, passwords and logins", this::showProfiles);
        settingLink(list, "lock", "Site permissions", "Reset saved camera, microphone and location answers", this::resetSitePermissions);
        settingLink(list, "trash", "Clear browsing data", null, this::clearData);
        settingLink(list, "info", "About SPS Browser", null, this::showAbout);

        ScrollView sv = new ScrollView(this);
        sv.addView(list);
        page.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        class SettingsPage extends LinearLayout implements Page {
            SettingsPage(Context c) { super(c); }
            @Override public boolean onBack() { return false; }
        }
        SettingsPage sp = new SettingsPage(this);
        sp.setOrientation(LinearLayout.VERTICAL);
        sp.addView(page, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        push(sp);
    }

    private void manageNeverSave() {
        if (neverSave.isEmpty()) { toast("No sites in this list"); return; }
        final String[] hosts = neverSave.toArray(new String[0]);
        final boolean[] on = new boolean[hosts.length];
        new AlertDialog.Builder(this).setTitle("Select sites to allow saving again")
                .setMultiChoiceItems(hosts, on, (dd, which, checked) -> on[which] = checked)
                .setPositiveButton("Allow", (dd, w) -> {
                    for (int i = 0; i < hosts.length; i++) if (on[i]) neverSave.remove(hosts[i]);
                    prefs.edit().putStringSet("neversave", new HashSet<>(neverSave)).apply();
                }).setNegativeButton("Cancel", null).show();
    }

    // ───────────────────────────── profiles ─────────────────────────────
    private static final int[] PROFILE_COLORS = {0xFF1A73E8, 0xFF188038, 0xFFE37400, 0xFFD93025, 0xFF9334E6, 0xFF129EAF, 0xFFC2185B, 0xFF5F6368};

    private void showProfiles() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(0, 0, 0, dp(14));
        TextView title = UI.text(this, "Profiles", 18, UI.TEXT, true);
        title.setPadding(dp(20), dp(10), dp(20), dp(4));
        box.addView(title);
        TextView note = UI.text(this, Profiles.separateCookies()
                ? "Each profile has its own bookmarks, history, passwords and logged-in sites."
                : "Each profile has its own bookmarks, history and passwords. On this Android version switching profile also signs you out of websites.", 12, UI.TEXT2, false);
        note.setPadding(dp(20), 0, dp(20), dp(8));
        box.addView(note);
        final Dialog[] d = new Dialog[1];
        for (final Profiles.Profile p : profiles.list()) {
            boolean active = p.id.equals(profiles.activeId());
            LinearLayout row = new LinearLayout(this);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setPadding(dp(18), dp(10), dp(8), dp(10));
            row.setBackground(UI.ripple(this, active ? UI.ACCENT_BG : Color.TRANSPARENT, 0, 0));
            row.addView(UI.avatar(this, p.name, p.color, 40));
            LinearLayout col = new LinearLayout(this);
            col.setOrientation(LinearLayout.VERTICAL);
            col.setPadding(dp(14), 0, 0, 0);
            col.addView(UI.oneLine(this, p.name, 16, UI.TEXT, true));
            col.addView(UI.oneLine(this, active ? "In use" : "Tap to switch", 12, active ? UI.ACCENT : UI.TEXT2, false));
            row.addView(col, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            ImageView edit = UI.icon(this, "edit", UI.TEXT2, 44, 11);
            edit.setOnClickListener(v -> { d[0].dismiss(); editProfile(p); });
            row.addView(edit);
            row.setOnClickListener(v -> {
                d[0].dismiss();
                if (!active) confirmSwitch(p);
            });
            box.addView(row);
        }
        LinearLayout add = UI.row(this, "plus", "Add profile", null, UI.ACCENT);
        add.setOnClickListener(v -> { d[0].dismiss(); editProfile(null); });
        box.addView(add);
        d[0] = UI.sheet(this, box);
        d[0].show();
    }

    private void confirmSwitch(final Profiles.Profile p) {
        new AlertDialog.Builder(this).setTitle("Switch to " + p.name + "?")
                .setMessage("SPS Browser restarts so the profile\u2019s own data can be opened. Your open tabs are saved and come back when you return.")
                .setPositiveButton("Switch", (dd, w) -> switchProfile(p.id))
                .setNegativeButton("Cancel", null).show();
    }

    private void editProfile(final Profiles.Profile existing) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(20), dp(10), dp(20), dp(4));
        final EditText name = UI.field(this, "Profile name", false);
        if (existing != null) name.setText(existing.name);
        box.addView(name);
        final int[] color = {existing != null ? existing.color : PROFILE_COLORS[profiles.list().size() % PROFILE_COLORS.length]};
        LinearLayout sw = new LinearLayout(this);
        sw.setPadding(0, dp(14), 0, 0);
        final List<View> dots = new ArrayList<>();
        for (final int col : PROFILE_COLORS) {
            View dot = new View(this);
            dots.add(dot);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(30), dp(30));
            lp.rightMargin = dp(8);
            sw.addView(dot, lp);
            final Runnable paint = () -> {
                for (int i = 0; i < PROFILE_COLORS.length; i++)
                    dots.get(i).setBackground(UI.box(this, PROFILE_COLORS[i], 15, PROFILE_COLORS[i] == color[0] ? UI.TEXT : 0));
            };
            dot.setOnClickListener(v -> { color[0] = col; paint.run(); });
        }
        box.addView(sw);
        for (int i = 0; i < PROFILE_COLORS.length; i++)
            dots.get(i).setBackground(UI.box(this, PROFILE_COLORS[i], 15, PROFILE_COLORS[i] == color[0] ? UI.TEXT : 0));
        AlertDialog.Builder b = new AlertDialog.Builder(this).setTitle(existing == null ? "New profile" : "Edit profile").setView(box)
                .setPositiveButton("Save", (dd, w) -> {
                    String n = name.getText().toString().trim();
                    if (n.isEmpty()) { toast("Enter a name"); return; }
                    if (existing == null) {
                        final Profiles.Profile np = profiles.add(n, color[0]);
                        new AlertDialog.Builder(this).setMessage("Profile \u201C" + n + "\u201D created. Switch to it now?")
                                .setPositiveButton("Switch", (d2, w2) -> switchProfile(np.id)).setNegativeButton("Later", null).show();
                    } else {
                        profiles.rename(existing.id, n, color[0]);
                        if (existing.id.equals(profiles.activeId())) {
                            profileAvatar.setText(n.substring(0, 1).toUpperCase());
                            profileAvatar.setBackground(UI.box(this, color[0], 17, 0));
                            android.graphics.drawable.GradientDrawable g = new android.graphics.drawable.GradientDrawable();
                            g.setShape(android.graphics.drawable.GradientDrawable.OVAL);
                            g.setColor(color[0]);
                            profileAvatar.setBackground(g);
                        }
                    }
                }).setNegativeButton("Cancel", null);
        if (existing != null && !existing.id.equals("default")) {
            b.setNeutralButton("Delete", (dd, w) -> new AlertDialog.Builder(this).setTitle("Delete " + existing.name + "?")
                    .setMessage("Its bookmarks, history, passwords and logins are erased for good.")
                    .setPositiveButton("Delete", (d2, w2) -> {
                        boolean wasActive = existing.id.equals(profiles.activeId());
                        profiles.delete(existing.id);
                        toast("Profile deleted");
                        if (wasActive) { switchingProfile = true; restartApp(); }
                    }).setNegativeButton("Cancel", null).show());
        }
        b.show();
    }

    private void switchProfile(String id) {
        saveSession();
        switchingProfile = true;
        if (!Profiles.separateCookies()) {                   // Android 8 and older cannot keep separate cookie jars: sign out instead of mixing profiles
            CookieManager.getInstance().removeAllCookies(null);
            CookieManager.getInstance().flush();
        }
        profiles.setActive(id);
        restartApp();
    }

    private void restartApp() {
        try { saveSession(); } catch (Exception ignored) { }
        Intent next = getPackageManager().getLaunchIntentForPackage(getPackageName());
        if (next != null) next.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        Intent r = new Intent(this, RestartActivity.class);        // lives in another process: ends this one, then opens the app again
        r.putExtra("next", next);
        r.putExtra("pid", android.os.Process.myPid());
        r.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(r);
    }

    private void saveSession() {
        try {
            JSONArray saved = new JSONArray();
            int index = 0;
            for (BTab t : tabs) {
                if (t.priv) continue;
                if (t == current) index = saved.length();
                JSONObject o = new JSONObject();
                o.put("u", isNewTab(t.url) ? "" : t.url);
                o.put("p", t.pinned);
                saved.put(o);
            }
            prefs.edit().putString("session", saved.toString()).putInt("session_index", index).apply();
        } catch (Exception ignored) { }
    }

    // ───────────────────────────── passwords and autofill ─────────────────────────────
    private static final String HOOK_JS =
            "(function(){if(window.__spsHook)return;window.__spsHook=true;"
            + "function find(f){var pw=f.querySelector('input[type=password]');if(!pw||!pw.value)return null;"
            + "var ins=[].slice.call(f.querySelectorAll('input'));var i=ins.indexOf(pw);var u='';"
            + "for(var k=i-1;k>=0;k--){var t=(ins[k].type||'text').toLowerCase();if((t=='text'||t=='email'||t=='tel')&&ins[k].value){u=ins[k].value;break;}}"
            + "return {u:u,p:pw.value};}"
            + "function report(f){try{var r=find(f);if(r)SPSAF.save(location.hostname,r.u,r.p);}catch(e){}}"
            + "document.addEventListener('submit',function(e){report(e.target);},true);"
            + "document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('button,input[type=submit],input[type=button],[role=button]');"
            + "if(!b)return;var f=b.form||b.closest('form')||document.body;report(f);},true);"
            + "document.addEventListener('keydown',function(e){if(e.key==='Enter'&&e.target&&e.target.type==='password'){report(e.target.form||document.body);}},true);"
            + "})();";

    /** Only the page can call save(); it can only ever propose saving, never read anything. The host is checked against the real address. */
    private class AutofillBridge {
        private final BTab tab;
        AutofillBridge(BTab t) { tab = t; }

        @JavascriptInterface
        public void save(final String host, final String user, final String pass) {
            runOnUiThread(() -> onLoginSubmitted(tab, host, user, pass));
        }
    }

    private void afterPageLoad(final BTab tab, final WebView view) {
        if (tab == current) updateChrome();
        final String url = tab.url;
        if (url == null || !url.startsWith("https://")) return;
        runExtensions(tab, view);
        if (offerSave && !tab.priv) view.evaluateJavascript(HOOK_JS, null);
        if (offerFill && tab == current && store.isSecure()) {
            final String host = UI.hostOf(url);
            final List<JSONObject> logins = store.loginsFor(host);
            if (logins.isEmpty()) return;
            view.evaluateJavascript("(function(){var p=document.querySelector('input[type=password]');return !!p&&p.offsetParent!==null})()", v -> {
                if ("true".equals(v) && tab == current && host.equals(UI.hostOf(tab.url))) offerFillBanner(host, logins);
            });
        }
    }

    private void onLoginSubmitted(BTab tab, String host, String user, String pass) {
        if (!offerSave || tab.priv || tab != current || host == null || pass == null || user == null) return;
        String url = tab.url;
        if (url == null || !url.startsWith("https://")) return;
        String real = UI.hostOf(url);
        String h = host.toLowerCase();
        if (h.startsWith("www.")) h = h.substring(4);
        if (!h.equals(real)) return;                                      // a frame trying to speak for another site
        if (pass.isEmpty() || pass.length() > 256 || user.length() > 256) return;
        if (neverSave.contains(real) || !store.isSecure()) return;
        if (store.samePassword(real, user, pass)) return;
        long now = System.currentTimeMillis();
        if (now - lastSaveOffer < 1500) return;
        lastSaveOffer = now;
        offerSaveBanner(real, user, pass, store.hasLogin(real, user));
    }

    private View banner(String icon, String title, String sub) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(dp(12), dp(10), dp(8), dp(10));
        card.setBackground(UI.box(this, UI.BG, 14, UI.BORDER));
        card.setElevation(dp(3));
        ImageView ic = new ImageView(this);
        ic.setImageDrawable(Ico.of(icon, UI.ACCENT));
        int pad = dp(8);
        ic.setPadding(pad, pad, pad, pad);
        ic.setBackground(UI.box(this, UI.ACCENT_BG, 18, 0));
        card.addView(ic, new LinearLayout.LayoutParams(dp(36), dp(36)));
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(dp(12), 0, dp(6), 0);
        col.addView(UI.oneLine(this, title, 14, UI.TEXT, true));
        col.addView(UI.oneLine(this, sub, 12, UI.TEXT2, false));
        card.addView(col, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return card;
    }

    private TextView bannerButton(String label, boolean primary, View.OnClickListener l) {
        TextView b = UI.text(this, label, 13, primary ? Color.WHITE : UI.ACCENT, true);
        b.setGravity(Gravity.CENTER);
        b.setPadding(dp(12), dp(8), dp(12), dp(8));
        b.setBackground(UI.ripple(this, primary ? UI.ACCENT : Color.TRANSPARENT, 16, 0));
        b.setOnClickListener(l);
        return b;
    }

    private void showBanner(View v) {
        bannerSlot.removeAllViews();
        bannerSlot.addView(v);
        bannerSlot.setVisibility(View.VISIBLE);
        final View mine = v;
        ui.postDelayed(() -> { if (bannerSlot.getChildCount() > 0 && bannerSlot.getChildAt(0) == mine) hideBanner(); }, 25000);
    }

    private void hideBanner() {
        if (bannerSlot == null) return;
        bannerSlot.removeAllViews();
        bannerSlot.setVisibility(View.GONE);
    }

    private void offerSaveBanner(final String host, final String user, final String pass, boolean update) {
        LinearLayout card = (LinearLayout) banner("key", update ? "Update saved password?" : "Save password?", (user.isEmpty() ? "(no username)" : user) + "  \u2022  " + host);
        card.addView(bannerButton("Never", false, v -> {
            neverSave.add(host);
            prefs.edit().putStringSet("neversave", new HashSet<>(neverSave)).apply();
            hideBanner();
        }));
        card.addView(bannerButton(update ? "Update" : "Save", true, v -> {
            hideBanner();
            if (store.saveLogin(null, host, user, pass, "")) toast(update ? "Password updated" : "Password saved (encrypted)");
            else toast("This phone cannot encrypt passwords, so nothing was saved");
        }));
        showBanner(card);
    }

    private void offerFillBanner(final String host, final List<JSONObject> logins) {
        String who = logins.get(0).optString("u");
        LinearLayout card = (LinearLayout) banner("key", "Sign in to " + host, (who.isEmpty() ? "Saved password" : who) + (logins.size() > 1 ? "  +" + (logins.size() - 1) + " more" : ""));
        card.addView(bannerButton("\u2715", false, v -> hideBanner()));
        card.addView(bannerButton("Fill", true, v -> {
            hideBanner();
            if (logins.size() == 1) fillLogin(logins.get(0)); else chooseLogin(logins);
        }));
        showBanner(card);
    }

    private void chooseLogin(final List<JSONObject> logins) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(0, 0, 0, dp(14));
        final Dialog[] d = new Dialog[1];
        TextView t = UI.text(this, "Choose an account", 18, UI.TEXT, true);
        t.setPadding(dp(20), dp(10), dp(20), dp(6));
        box.addView(t);
        for (final JSONObject o : logins) {
            LinearLayout row = UI.row(this, "user", o.optString("u").isEmpty() ? "(no username)" : o.optString("u"), o.optString("h"), UI.TEXT2);
            row.setOnClickListener(v -> { d[0].dismiss(); fillLogin(o); });
            box.addView(row);
        }
        d[0] = UI.sheet(this, box);
        d[0].show();
    }

    private void fillLogin(final JSONObject login) {
        unlock(() -> {
            if (current == null) return;
            String js = "(function(u,p){function set(e,v){var s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(e,v);"
                    + "e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}"
                    + "var pw=[].slice.call(document.querySelectorAll('input[type=password]')).filter(function(e){return e.offsetParent!==null;})[0];if(!pw)return 0;"
                    + "var root=pw.form||document;var ins=[].slice.call(root.querySelectorAll('input'));var i=ins.indexOf(pw);var us=null;"
                    + "for(var k=i-1;k>=0;k--){var t=(ins[k].type||'text').toLowerCase();if(t=='text'||t=='email'||t=='tel'){us=ins[k];break;}}"
                    + "if(us&&u)set(us,u);set(pw,p);return 1;})(" + JSONObject.quote(login.optString("u")) + "," + JSONObject.quote(login.optString("p")) + ")";
            current.web.evaluateJavascript(js, null);
        });
    }

    /** "Fill form": puts the saved name / email / phone / address into the form on the page. */
    private void fillAddress() {
        final JSONObject a = store.autofill();
        if (a.length() == 0) {
            new AlertDialog.Builder(this).setMessage("Add your autofill info first (name, email, address ...).")
                    .setPositiveButton("Add", (dd, w) -> Vault.openAutofill(this)).setNegativeButton("Cancel", null).show();
            return;
        }
        unlock(() -> {
            if (current == null) return;
            String js = "(function(d){function key(e){return ((e.getAttribute('autocomplete')||'')+' '+(e.name||'')+' '+(e.id||'')+' '+(e.placeholder||'')+' '+(e.getAttribute('aria-label')||'')).toLowerCase();}"
                    + "function set(e,v){if(!v||e.disabled||e.readOnly)return;"
                    + "var P=e.tagName=='SELECT'?HTMLSelectElement.prototype:e.tagName=='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;var s=Object.getOwnPropertyDescriptor(P,'value');"
                    + "if(e.tagName=='SELECT'){for(var i=0;i<e.options.length;i++){var o=e.options[i];if(o.text.toLowerCase()==v.toLowerCase()||o.value.toLowerCase()==v.toLowerCase()){s.set.call(e,o.value);break;}}}else s.set.call(e,v);"
                    + "e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}"
                    + "var parts=(d.name||'').split(' ');var first=parts[0]||'',last=parts.slice(1).join(' ');var n=0;"
                    + "[].slice.call(document.querySelectorAll('input,select,textarea')).forEach(function(e){var t=(e.type||'').toLowerCase();"
                    + "if(['password','hidden','checkbox','radio','submit','button','file'].indexOf(t)>=0)return;var k=key(e);if(/user(name)?|login|captcha|search/.test(k)&&!/e-?mail/.test(k))return;var v='';"
                    + "if(/e-?mail/.test(k))v=d.email;else if(/tel|phone|mobile/.test(k))v=d.phone;else if(/zip|postal|postcode/.test(k))v=d.zip;"
                    + "else if(/city|town|address-level2/.test(k))v=d.city;else if(/state|region|province|address-level1/.test(k))v=d.state;else if(/country/.test(k))v=d.country;"
                    + "else if(/organi[sz]ation|company/.test(k))v=d.org;else if(/given-name|first/.test(k))v=first;else if(/family-name|last|surname/.test(k))v=last;"
                    + "else if(/street|address-line1|address1|addr|address/.test(k))v=d.addr;else if(/name/.test(k))v=d.name;"
                    + "if(v){set(e,v);n++;}});return n;})(" + a.toString() + ")";
            current.web.evaluateJavascript(js, r -> toast("0".equals(r) || r == null ? "No matching fields found on this page" : "Form filled"));
        });
    }





    // ───────────────────────────── SPS extensions (store + user scripts) ─────────────────────────────
    private void runExtensions(BTab tab, WebView view) {
        String host = UI.hostOf(tab.url);
        if (host.isEmpty()) return;
        StringBuilder all = new StringBuilder();
        for (Extensions.Def d : Extensions.CATALOG) {
            if (!extOn.contains(d.id) || extSiteOff.contains(d.id + "|" + host)) continue;
            all.append(Extensions.js(d.id, prefs.getInt("ext_opt_" + d.id, d.defaultOption))).append('\n');
        }
        for (int i = 0; i < userScripts.length(); i++) {
            JSONObject o = userScripts.optJSONObject(i);
            if (o == null || !o.optBoolean("on", true) || !Extensions.hostMatches(o.optString("m", "*"), host)) continue;
            String css = o.optString("css", ""), code = o.optString("js", "");
            if (!css.isEmpty()) all.append("(function(){var s=document.createElement('style');s.textContent=").append(Extensions.quote(css)).append(";(document.head||document.documentElement).appendChild(s);})();\n");
            if (!code.isEmpty()) all.append("try{").append(code).append("\n}catch(e){}\n");
        }
        if (all.length() > 0) view.evaluateJavascript("(function(){" + all + "})();", null);
    }

    private void saveExt() {
        prefs.edit().putStringSet("ext_on", new HashSet<>(extOn)).putStringSet("ext_siteoff", new HashSet<>(extSiteOff))
                .putString("ext_user", userScripts.toString()).apply();
    }

    private void showExtensions() {
        class ExtPage extends LinearLayout implements Page {
            ExtPage(Context c) { super(c); }
            @Override public boolean onBack() { return false; }
        }
        ExtPage page = new ExtPage(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setBackgroundColor(UI.BG);
        page.setClickable(true);
        page.addView(Vault.topBar(this, "Extension store"));
        page.addView(UI.divider(this));
        final LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setPadding(dp(12), dp(8), dp(12), dp(30));
        ScrollView sv = new ScrollView(this);
        sv.addView(list);
        page.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        fillExtensions(list);
        push(page);
    }

    private void fillExtensions(final LinearLayout list) {
        list.removeAllViews();
        TextView intro = UI.text(this, "Add-ons that run inside web pages. Chrome extension files cannot run on Android, so SPS ships its own and lets you write your own.", 12, UI.TEXT2, false);
        intro.setPadding(dp(8), dp(4), dp(8), dp(10));
        list.addView(intro);
        for (final Extensions.Def d : Extensions.CATALOG) {
            final boolean on = extOn.contains(d.id);
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setPadding(dp(16), dp(14), dp(16), dp(12));
            card.setBackground(UI.box(this, on ? UI.ACCENT_BG : 0xFFF5F6F8, 18, 0));
            LinearLayout top = new LinearLayout(this);
            top.setGravity(Gravity.CENTER_VERTICAL);
            ImageView ic = new ImageView(this);
            ic.setImageDrawable(Ico.of(d.icon, UI.ACCENT));
            top.addView(ic, new LinearLayout.LayoutParams(dp(26), dp(26)));
            LinearLayout col = new LinearLayout(this);
            col.setOrientation(LinearLayout.VERTICAL);
            col.setPadding(dp(12), 0, dp(8), 0);
            col.addView(UI.text(this, d.name, 16, UI.TEXT, true));
            col.addView(UI.text(this, d.desc, 12, UI.TEXT2, false));
            top.addView(col, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            TextView btn = UI.button(this, on ? "Remove" : "Add", !on);
            btn.setOnClickListener(v -> {
                if (on) extOn.remove(d.id); else extOn.add(d.id);
                saveExt(); fillExtensions(list); toast(on ? d.name + " removed" : d.name + " added \u2014 applies to pages you open next");
            });
            top.addView(btn);
            card.addView(top);
            if (on) {
                LinearLayout row = new LinearLayout(this);
                row.setPadding(0, dp(8), 0, 0);
                if (d.options != null) {
                    int cur = prefs.getInt("ext_opt_" + d.id, d.defaultOption);
                    TextView st = UI.button(this, "Setting: " + d.options[Math.max(0, Math.min(d.options.length - 1, cur))], false);
                    st.setOnClickListener(v -> new AlertDialog.Builder(this).setTitle(d.name)
                            .setSingleChoiceItems(d.options, prefs.getInt("ext_opt_" + d.id, d.defaultOption), (dd, which) -> {
                                prefs.edit().putInt("ext_opt_" + d.id, which).apply(); dd.dismiss(); fillExtensions(list);
                                if (current != null) current.web.reload();
                            }).show());
                    row.addView(st);
                }
                final String host = current == null || isNewTab(current.url) ? "" : UI.hostOf(current.url);
                if (!host.isEmpty()) {
                    final boolean off = extSiteOff.contains(d.id + "|" + host);
                    TextView sb = UI.button(this, off ? "Allow on " + host : "Off on " + host, false);
                    sb.setOnClickListener(v -> {
                        if (off) extSiteOff.remove(d.id + "|" + host); else extSiteOff.add(d.id + "|" + host);
                        saveExt(); fillExtensions(list); if (current != null) current.web.reload();
                    });
                    row.addView(sb);
                }
                card.addView(row);
            }
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.setMargins(0, 0, 0, dp(10));
            list.addView(card, lp);
        }
        TextView hd = UI.text(this, "YOUR OWN SCRIPTS", 12, UI.TEXT2, true);
        hd.setPadding(dp(8), dp(10), dp(8), dp(6));
        list.addView(hd);
        for (int i = 0; i < userScripts.length(); i++) {
            final int idx = i;
            final JSONObject o = userScripts.optJSONObject(i);
            if (o == null) continue;
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setPadding(dp(16), dp(12), dp(16), dp(10));
            card.setBackground(UI.box(this, 0xFFF5F6F8, 18, 0));
            card.addView(UI.text(this, o.optString("n", "Script"), 15, UI.TEXT, true));
            card.addView(UI.text(this, "Runs on: " + o.optString("m", "*") + (o.optBoolean("on", true) ? "" : "   (off)"), 12, UI.TEXT2, false));
            LinearLayout row = new LinearLayout(this);
            TextView t1 = UI.button(this, o.optBoolean("on", true) ? "Turn off" : "Turn on", false);
            t1.setOnClickListener(v -> { try { o.put("on", !o.optBoolean("on", true)); } catch (Exception ignored) { } saveExt(); fillExtensions(list); });
            TextView t2 = UI.button(this, "Delete", false);
            t2.setOnClickListener(v -> new AlertDialog.Builder(this).setTitle("Delete this script?")
                    .setPositiveButton("Delete", (dd, w) -> { userScripts.remove(idx); saveExt(); fillExtensions(list); })
                    .setNegativeButton("Cancel", null).show());
            row.addView(t1); row.addView(t2);
            card.addView(row);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.setMargins(0, 0, 0, dp(10));
            list.addView(card, lp);
        }
        TextView add = UI.button(this, "+ Write a script / style", true);
        add.setOnClickListener(v -> addUserScript(list));
        list.addView(add);
    }

    private void addUserScript(final LinearLayout list) {
        LinearLayout f = new LinearLayout(this);
        f.setOrientation(LinearLayout.VERTICAL);
        f.setPadding(dp(20), dp(8), dp(20), 0);
        final EditText name = new EditText(this); name.setHint("Name"); name.setSingleLine(true);
        final EditText match = new EditText(this); match.setHint("Websites: * or example.com or *.example.com"); match.setText("*"); match.setSingleLine(true);
        final EditText css = new EditText(this); css.setHint("CSS (optional)"); css.setMinLines(2);
        final EditText js = new EditText(this); js.setHint("JavaScript (optional)"); js.setMinLines(3);
        f.addView(name); f.addView(match); f.addView(css); f.addView(js);
        ScrollView sc = new ScrollView(this); sc.addView(f);
        new AlertDialog.Builder(this).setTitle("New script").setView(sc)
                .setPositiveButton("Save", (d, w) -> {
                    try {
                        JSONObject o = new JSONObject();
                        o.put("n", name.getText().toString().trim().isEmpty() ? "My script" : name.getText().toString().trim());
                        o.put("m", match.getText().toString().trim().isEmpty() ? "*" : match.getText().toString().trim());
                        o.put("css", css.getText().toString()); o.put("js", js.getText().toString()); o.put("on", true);
                        userScripts.put(o); saveExt(); fillExtensions(list);
                    } catch (Exception ignored) { }
                }).setNegativeButton("Cancel", null).show();
    }


    // ───────────────────────────── saved site permissions ─────────────────────────────
    private void manageSitePermissions() {
        final ArrayList<String> keys = new ArrayList<>(), labels = new ArrayList<>();
        for (java.util.Map.Entry<String, ?> e : prefs.getAll().entrySet()) {
            String k = e.getKey();
            if (!k.startsWith("perm:") || !(e.getValue() instanceof String)) continue;
            String rest = k.substring(5);
            int cut = rest.lastIndexOf(':');
            if (cut < 0) continue;
            keys.add(k);
            labels.add(rest.substring(0, cut) + "  \u2014  " + rest.substring(cut + 1) + ": " + (e.getValue().equals("allow") ? "allowed" : "blocked"));
        }
        if (keys.isEmpty()) { toast("No saved site permissions"); return; }
        final boolean[] sel = new boolean[keys.size()];
        new AlertDialog.Builder(this).setTitle("Saved site permissions (select to reset)")
                .setMultiChoiceItems(labels.toArray(new String[0]), sel, (d, w, c) -> sel[w] = c)
                .setPositiveButton("Reset selected", (d, w) -> {
                    SharedPreferences.Editor ed = prefs.edit();
                    int n = 0;
                    for (int i = 0; i < sel.length; i++) if (sel[i]) { ed.remove(keys.get(i)); n++; }
                    ed.apply(); toast(n + " reset \u2014 the site will ask again");
                })
                .setNeutralButton("Reset all", (d, w) -> {
                    SharedPreferences.Editor ed = prefs.edit();
                    for (String k : keys) ed.remove(k);
                    ed.apply(); toast("All site permissions reset");
                })
                .setNegativeButton("Close", null).show();
    }


    // ───────────────────────────── app updates (GitHub release of this project) ─────────────────────────────
    private String updateRepo() {
        int id = getResources().getIdentifier("update_repo", "string", getPackageName());
        return id == 0 ? "" : getString(id).trim();
    }

    private String myVersion() {
        try { return getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Exception e) { return "0"; }
    }

    private static String fetchText(String url) throws Exception {
        java.net.HttpURLConnection c = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();
        c.setConnectTimeout(12000); c.setReadTimeout(20000);
        c.setRequestProperty("Accept", "application/vnd.github+json");
        c.setRequestProperty("User-Agent", "SPS-Browser-Android");
        if (c.getResponseCode() != 200) throw new java.io.IOException("HTTP " + c.getResponseCode());
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        try (java.io.InputStream in = c.getInputStream()) {
            byte[] b = new byte[8192]; int n;
            while ((n = in.read(b)) > 0 && out.size() < 2_000_000) out.write(b, 0, n);
        }
        return out.toString("UTF-8");
    }

    /** manual = the user pressed "Check for updates" (always answers); otherwise it runs quietly at most every 12 hours. */
    private void checkForUpdate(final boolean manual) {
        final String repo = updateRepo();
        if (repo.isEmpty() || !repo.matches("[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")) {
            if (manual) toast("Updates are not set up in this build (it was not built by the project's GitHub workflow)");
            return;
        }
        if (!manual) {
            long last = prefs.getLong("update_checked", 0);
            if (System.currentTimeMillis() - last < 12L * 3600 * 1000) return;
        }
        if (manual) toast("Checking for updates...");
        new Thread(() -> {
            try {
                final Updater.Info info = Updater.fromRelease(fetchText("https://api.github.com/repos/" + repo + "/releases/latest"));
                prefs.edit().putLong("update_checked", System.currentTimeMillis()).apply();
                runOnUiThread(() -> {
                    if (isFinishing()) return;
                    if (info != null && Updater.isNewer(info.version, myVersion())) offerUpdate(info);
                    else if (manual) toast("You have the latest version (" + myVersion() + ")");
                });
            } catch (Exception e) {
                if (manual) runOnUiThread(() -> toast("Could not check for updates: " + e.getMessage()));
            }
        }, "sps-update-check").start();
    }

    private void offerUpdate(final Updater.Info info) {
        String size = info.size > 0 ? "  (" + android.text.format.Formatter.formatShortFileSize(this, info.size) + ")" : "";
        String notes = info.notes == null ? "" : info.notes.trim();
        if (notes.length() > 600) notes = notes.substring(0, 600) + "...";
        new AlertDialog.Builder(this).setTitle("SPS Browser " + info.version + " is available")
                .setMessage("You have " + myVersion() + size + ".\n\nThe file is checked (SHA-256) and Android only installs it if it is signed with the same key as this app.\n\n" + notes)
                .setPositiveButton("Download & install", (d, w) -> downloadUpdate(info))
                .setNegativeButton("Later", null).show();
    }

    private void downloadUpdate(final Updater.Info info) {
        if (downloadingUpdate >= 0) { toast("Already downloading"); return; }
        DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
        if (dm == null) { toast("Downloads are not available"); return; }
        DownloadManager.Request r = new DownloadManager.Request(Uri.parse(info.apkUrl));
        r.setTitle("SPS Browser " + info.version);
        r.setMimeType("application/vnd.android.package-archive");
        r.setDestinationInExternalFilesDir(this, Environment.DIRECTORY_DOWNLOADS, "update-" + info.version + ".apk");
        r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE);
        downloadingUpdate = dm.enqueue(r);
        toast("Downloading the update...");
        pollUpdate(info);
    }

    private void pollUpdate(final Updater.Info info) {
        ui.postDelayed(() -> {
            DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
            Cursor c = null;
            try {
                c = dm.query(new DownloadManager.Query().setFilterById(downloadingUpdate));
                if (c == null || !c.moveToFirst()) { downloadingUpdate = -1; return; }
                int st = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
                if (st == DownloadManager.STATUS_SUCCESSFUL) {
                    long id = downloadingUpdate; downloadingUpdate = -1;
                    verifyAndInstall(info, dm.getUriForDownloadedFile(id), id);
                } else if (st == DownloadManager.STATUS_FAILED) {
                    downloadingUpdate = -1; toast("The update download failed");
                } else pollUpdate(info);
            } catch (Exception e) {
                downloadingUpdate = -1;
            } finally { if (c != null) c.close(); }
        }, 1000);
    }

    private void verifyAndInstall(final Updater.Info info, final Uri file, final long dlId) {
        new Thread(() -> {
            String problem = null;
            try {
                String want = null;
                if (info.sumsUrl != null) want = Updater.hashFor(fetchText(info.sumsUrl), info.apkName);
                if (want == null) problem = "The release has no checksum for this file";
                else {
                    String got;
                    try (java.io.InputStream in = getContentResolver().openInputStream(file)) { got = Updater.sha256(in); }
                    if (!got.equals(want)) problem = "The downloaded file does not match its checksum";
                }
            } catch (Exception e) { problem = "Could not check the file: " + e.getMessage(); }
            final String bad = problem;
            runOnUiThread(() -> {
                if (bad != null) {
                    try { ((DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE)).remove(dlId); } catch (Exception ignored) { }
                    new AlertDialog.Builder(this).setTitle("Update not installed").setMessage(bad + ". The file was deleted for your safety.").setPositiveButton("OK", null).show();
                    return;
                }
                installApk(file);
            });
        }, "sps-update-verify").start();
    }

    private void installApk(Uri file) {
        if (Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
            new AlertDialog.Builder(this).setTitle("Allow installing updates")
                    .setMessage("Android needs your permission once so SPS Browser can install its own updates. Turn it on, then press Check for updates again.")
                    .setPositiveButton("Open settings", (d, w) -> startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName()))))
                    .setNegativeButton("Cancel", null).show();
            return;
        }
        try {
            Intent i = new Intent(Intent.ACTION_VIEW);
            i.setDataAndType(file, "application/vnd.android.package-archive");
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (Exception e) { toast("Could not open the installer"); }
    }


    // ───────────────────────────── read aloud / home-screen shortcut ─────────────────────────────
    private android.speech.tts.TextToSpeech tts;
    private boolean ttsSpeaking;

    private void readAloud() {
        if (current == null || isNewTab(current.url)) { toast("Open a page first"); return; }
        if (tts != null && ttsSpeaking) { tts.stop(); ttsSpeaking = false; toast("Stopped"); return; }
        current.web.evaluateJavascript("(function(){var t=document.body?document.body.innerText:'';return t.substring(0,6000);})()", value -> {
            String text = "";
            try { Object o = new org.json.JSONTokener(value == null ? "\"\"" : value).nextValue(); text = o == null ? "" : String.valueOf(o); } catch (Exception ignored) { }
            if (text.trim().isEmpty()) { toast("Nothing to read on this page"); return; }
            final String say = text;
            if (tts == null) {
                tts = new android.speech.tts.TextToSpeech(getApplicationContext(), status -> {
                    if (status == android.speech.tts.TextToSpeech.SUCCESS) { tts.setLanguage(Locale.getDefault()); speak(say); }
                    else { toast("Text-to-speech is not available on this phone"); tts = null; }
                });
            } else speak(say);
        });
    }

    private void speak(String text) {
        ttsSpeaking = true;
        tts.speak(text, android.speech.tts.TextToSpeech.QUEUE_FLUSH, null, "sps-read");
        toast("Reading aloud - open the menu to stop");
    }

    private void addToHomeScreen() {
        if (current == null || isNewTab(current.url)) { toast("Open a page first"); return; }
        if (Build.VERSION.SDK_INT < 26) { toast("Needs Android 8 or newer"); return; }
        android.content.pm.ShortcutManager sm = getSystemService(android.content.pm.ShortcutManager.class);
        if (sm == null || !sm.isRequestPinShortcutSupported()) { toast("Your launcher does not support home-screen shortcuts"); return; }
        String title = current.title == null || current.title.isEmpty() ? UI.hostOf(current.url) : current.title;
        Bitmap bmp = Bitmap.createBitmap(192, 192, Bitmap.Config.ARGB_8888);
        android.graphics.Canvas cv = new android.graphics.Canvas(bmp);
        android.graphics.Paint p = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        p.setColor(UI.ACCENT);
        cv.drawCircle(96, 96, 96, p);
        p.setColor(Color.WHITE); p.setTextSize(110); p.setTextAlign(android.graphics.Paint.Align.CENTER); p.setTypeface(Typeface.DEFAULT_BOLD);
        cv.drawText(title.substring(0, 1).toUpperCase(), 96, 134, p);
        Intent open = new Intent(Intent.ACTION_VIEW, Uri.parse(current.url), this, MainActivity.class);
        android.content.pm.ShortcutInfo info = new android.content.pm.ShortcutInfo.Builder(this, "sps-" + Integer.toHexString(current.url.hashCode()))
                .setShortLabel(title.length() > 24 ? title.substring(0, 24) : title)
                .setIcon(android.graphics.drawable.Icon.createWithBitmap(bmp)).setIntent(open).build();
        sm.requestPinShortcut(info, null);
    }


    // ───────────────────────────── Lens search (photo -> Google Lens) ─────────────────────────────
    private void startLens() {
        new AlertDialog.Builder(this).setTitle("Search with Lens")
                .setItems(new String[]{"Take a photo", "Choose a photo"}, (d, which) -> {
                    if (which == 0) {
                        if (checkSelfPermission(android.Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED)
                            requestPermissions(new String[]{android.Manifest.permission.CAMERA}, REQ_LENS_PERM);
                        else lensCapture();
                    } else {
                        lensCamera = null;
                        Intent pick = new Intent(Intent.ACTION_GET_CONTENT);
                        pick.addCategory(Intent.CATEGORY_OPENABLE);
                        pick.setType("image/*");
                        try { startActivityForResult(pick, REQ_LENS); } catch (Exception e) { toast("No gallery app found"); }
                    }
                }).setNegativeButton("Cancel", null).show();
    }

    private void lensCapture() {
        try {
            android.content.ContentValues cv = new android.content.ContentValues();
            cv.put(android.provider.MediaStore.Images.Media.DISPLAY_NAME, "SPS_lens_" + System.currentTimeMillis() + ".jpg");
            cv.put(android.provider.MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
            lensCamera = getContentResolver().insert(android.provider.MediaStore.Images.Media.EXTERNAL_CONTENT_URI, cv);
            if (lensCamera == null) throw new IllegalStateException();
            Intent it = new Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE);
            it.putExtra(android.provider.MediaStore.EXTRA_OUTPUT, lensCamera);
            it.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivityForResult(it, REQ_LENS);
        } catch (Exception e) { toast("Camera is not available"); }
    }

    private void onLensPicked(int resultCode, Intent data) {
        final Uri cam = lensCamera;
        lensCamera = null;
        final Uri src = resultCode == RESULT_OK ? (data != null && data.getData() != null ? data.getData() : cam) : null;
        if (src == null) {
            if (cam != null) { try { getContentResolver().delete(cam, null, null); } catch (Exception ignored) { } }
            return;
        }
        toast("Preparing the photo...");
        new Thread(() -> {
            String b64 = null;
            try {
                BitmapFactory.Options o = new BitmapFactory.Options();
                o.inJustDecodeBounds = true;
                try (java.io.InputStream in = getContentResolver().openInputStream(src)) { BitmapFactory.decodeStream(in, null, o); }
                int sample = 1;
                while (Math.max(o.outWidth, o.outHeight) / sample > 1600) sample *= 2;
                BitmapFactory.Options o2 = new BitmapFactory.Options();
                o2.inSampleSize = sample;
                Bitmap bmp;
                try (java.io.InputStream in = getContentResolver().openInputStream(src)) { bmp = BitmapFactory.decodeStream(in, null, o2); }
                int rot = 0;
                try (java.io.InputStream in = getContentResolver().openInputStream(src)) {
                    int ori = new android.media.ExifInterface(in).getAttributeInt(android.media.ExifInterface.TAG_ORIENTATION, 1);
                    rot = ori == 6 ? 90 : ori == 3 ? 180 : ori == 8 ? 270 : 0;
                } catch (Exception ignored) { }
                if (bmp != null && rot != 0) {
                    android.graphics.Matrix m = new android.graphics.Matrix(); m.postRotate(rot);
                    bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.getWidth(), bmp.getHeight(), m, true);
                }
                if (bmp != null) {
                    java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
                    bmp.compress(Bitmap.CompressFormat.JPEG, 85, out);
                    b64 = android.util.Base64.encodeToString(out.toByteArray(), android.util.Base64.NO_WRAP);
                }
            } catch (Exception ignored) { }
            if (cam != null) { try { getContentResolver().delete(cam, null, null); } catch (Exception ignored) { } }   // do not leave the photo in the gallery
            final String data64 = b64;
            runOnUiThread(() -> {
                if (data64 == null) { toast("That photo could not be read"); return; }
                BTab t = newTab(null, false, true);
                t.web.loadDataWithBaseURL("https://lens.google.com/", Lens.uploadPage(Lens.UPLOAD, Lens.FIELD, data64), "text/html", "utf-8", null);
            });
        }, "sps-lens").start();
    }

    // ───────────────────────────── page tools ─────────────────────────────
    private void showTools() {
        final boolean page = current != null && !isNewTab(current.url);
        final ArrayList<String> labels = new ArrayList<>();
        final ArrayList<Runnable> acts = new ArrayList<>();
        if (page) {
            labels.add("Screenshot of this page"); acts.add(this::screenshotPage);
            labels.add("Page information"); acts.add(this::pageInfo);
            labels.add("View page source"); acts.add(this::viewSource);
            labels.add("Copy all page text"); acts.add(this::copyPageText);
            labels.add("Print / Save page as PDF"); acts.add(this::printPage);
            labels.add("Print selected area"); acts.add(this::printSelectedArea);
            labels.add("Share this page"); acts.add(() -> startActivity(Intent.createChooser(new Intent(Intent.ACTION_SEND).setType("text/plain")
                    .putExtra(Intent.EXTRA_TEXT, current.url).putExtra(Intent.EXTRA_SUBJECT, current.title), "Share page")));
            labels.add("Scroll to top"); acts.add(() -> current.web.scrollTo(0, 0));
            labels.add("Scroll to bottom"); acts.add(() -> current.web.evaluateJavascript("window.scrollTo(0,document.body.scrollHeight)", null));
        }
        labels.add("Open link from clipboard"); acts.add(this::pasteAndGo);
        labels.add("Search with Lens"); acts.add(this::startLens);
        labels.add("Voice search"); acts.add(this::voiceSearch);
        new AlertDialog.Builder(this).setTitle("Page tools")
                .setItems(labels.toArray(new String[0]), (d, which) -> acts.get(which).run()).show();
    }

    private void screenshotPage() {
        if (current == null || current.web.getWidth() <= 0) return;
        captureArea(current.web, new android.graphics.Rect(0, 0, current.web.getWidth(), current.web.getHeight()), bmp -> {
            if (bmp == null) { toast("Could not take the screenshot"); return; }
            android.net.Uri u = saveBitmapToPictures(bmp);
            toast(u == null ? "Could not save the screenshot" : "Saved to Pictures/SPS");
        });
    }

    private void pageInfo() {
        if (current == null) return;
        StringBuilder sb = new StringBuilder();
        sb.append("Title: ").append(current.title).append("\n\nAddress: ").append(current.url).append("\n\n");
        boolean https = current.url != null && current.url.startsWith("https://");
        sb.append("Connection: ").append(https ? "encrypted (https)" : "NOT encrypted").append('\n');
        android.net.http.SslCertificate c = current.web.getCertificate();
        if (c != null) {
            sb.append("Issued to: ").append(c.getIssuedTo() == null ? "?" : c.getIssuedTo().getCName()).append('\n');
            sb.append("Issued by: ").append(c.getIssuedBy() == null ? "?" : c.getIssuedBy().getCName()).append('\n');
            sb.append("Valid until: ").append(c.getValidNotAfterDate()).append('\n');
        }
        sb.append("\nPrivacy shield here: ").append(shieldOff.contains(UI.hostOf(current.url)) ? "paused" : (adBlock ? "on" : "off"));
        new AlertDialog.Builder(this).setTitle("Page information").setMessage(sb.toString()).setPositiveButton("OK", null).show();
    }

    private void viewSource() {
        if (current == null) return;
        current.web.evaluateJavascript("document.documentElement.outerHTML", value -> {
            String src = "";
            try { Object o = new org.json.JSONTokener(value == null ? "\"\"" : value).nextValue(); src = o == null ? "" : String.valueOf(o); } catch (Exception ignored) { }
            BTab t = newTab(null, false, true);
            t.web.loadDataWithBaseURL("about:blank", "<html><head><meta name='viewport' content='width=device-width'></head><body style='margin:8px'><pre style='white-space:pre-wrap;word-break:break-all;font-size:12px'>"
                    + android.text.TextUtils.htmlEncode(src) + "</pre></body></html>", "text/html", "utf-8", null);
        });
    }

    private void copyPageText() {
        if (current == null) return;
        current.web.evaluateJavascript("document.body?document.body.innerText:''", value -> {
            String text = "";
            try { Object o = new org.json.JSONTokener(value == null ? "\"\"" : value).nextValue(); text = o == null ? "" : String.valueOf(o); } catch (Exception ignored) { }
            if (text.trim().isEmpty()) toast("Nothing to copy"); else { copyText(text); }
        });
    }

    private void pasteAndGo() {
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        CharSequence t = null;
        if (cm != null && cm.hasPrimaryClip() && cm.getPrimaryClip().getItemCount() > 0) t = cm.getPrimaryClip().getItemAt(0).getText();
        if (t == null || t.toString().trim().isEmpty()) { toast("The clipboard is empty"); return; }
        go(t.toString());
    }

    // ───────────────────────────── thought of the day ─────────────────────────────
    private void showQuote(boolean next) {
        if (next) quoteIndex++; else quoteIndex = Quotes.today();
        final String[] q = Quotes.at(quoteIndex);
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(24), dp(22), dp(24), dp(14));
        card.setBackground(UI.box(this, UI.BG, 26, 0));
        TextView mark = UI.text(this, "\u201C", 54, UI.ACCENT, true);
        mark.setIncludeFontPadding(false);
        card.addView(mark);
        TextView body = UI.text(this, q[0], 19, UI.TEXT, false);
        body.setTypeface(Typeface.SERIF, Typeface.ITALIC);
        body.setLineSpacing(0, 1.2f);
        card.addView(body);
        TextView who = UI.text(this, "\u2014 " + q[1], 14, UI.ACCENT, true);
        who.setPadding(0, dp(14), 0, dp(14));
        card.addView(who);
        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.END);
        TextView nextB = UI.button(this, "Next", false), copyB = UI.button(this, "Copy", false), okB = UI.button(this, "Close", true);
        row.addView(nextB); row.addView(copyB); row.addView(okB);
        card.addView(row);
        final AlertDialog d = new AlertDialog.Builder(this).setView(card).create();
        if (d.getWindow() != null) d.getWindow().setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(Color.TRANSPARENT));
        nextB.setOnClickListener(v -> { d.dismiss(); showQuote(true); });
        copyB.setOnClickListener(v -> {
            ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
            if (cm != null) cm.setPrimaryClip(ClipData.newPlainText("quote", "\u201C" + q[0] + "\u201D \u2014 " + q[1]));
            toast("Copied");
        });
        okB.setOnClickListener(v -> d.dismiss());
        d.show();
    }

    private void maybeShowDailyQuote() {
        if (!dailyQuote) return;
        String key = new java.text.SimpleDateFormat("yyyyMMdd", Locale.US).format(new java.util.Date());
        if (key.equals(prefs.getString("quote_day", ""))) return;
        prefs.edit().putString("quote_day", key).apply();
        root.postDelayed(() -> { if (!isFinishing() && lockOverlay == null) showQuote(false); }, 900);
    }

    // ───────────────────────────── privacy shield page ─────────────────────────────
    private void showShield() {
        if (current == null) return;
        final String host = isNewTab(current.url) ? "" : UI.hostOf(current.url);
        class ShieldPage extends LinearLayout implements Page {
            ShieldPage(Context c) { super(c); }
            @Override public boolean onBack() { return false; }
        }
        ShieldPage root2 = new ShieldPage(this);
        root2.setOrientation(LinearLayout.VERTICAL);
        root2.setBackgroundColor(UI.BG);
        root2.setClickable(true);
        root2.addView(Vault.topBar(this, "Privacy shield"));
        root2.addView(UI.divider(this));
        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setPadding(0, 0, 0, dp(30));

        LinearLayout hero = new LinearLayout(this);
        hero.setOrientation(LinearLayout.VERTICAL);
        hero.setGravity(Gravity.CENTER);
        hero.setPadding(dp(20), dp(22), dp(20), dp(22));
        hero.setBackground(UI.box(this, UI.ACCENT_BG, 18, 0));
        ImageView sh = new ImageView(this);
        sh.setImageDrawable(Ico.of("shield", UI.ACCENT));
        hero.addView(sh, new LinearLayout.LayoutParams(dp(40), dp(40)));
        TextView big = UI.text(this, String.valueOf(blockedCount.get()), 38, UI.ACCENT, true);
        hero.addView(big);
        hero.addView(UI.text(this, "trackers & ads blocked this session", 13, UI.TEXT2, false));
        hero.addView(UI.text(this, (blockedTotal + blockedCount.get() - blockedSaved) + " in total", 12, UI.TEXT3, false));
        LinearLayout.LayoutParams hp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        hp.setMargins(dp(16), dp(14), dp(16), dp(6));
        list.addView(hero, hp);

        if (!host.isEmpty()) {
            settingHeader(list, "This site: " + host);
            settingSwitch(list, "Shield on this site", shieldOff.contains(host) ? "Paused - ads and trackers are allowed here" : "Active", !shieldOff.contains(host), v -> {
                if (v) shieldOff.remove(host); else shieldOff.add(host);
                prefs.edit().putStringSet("shieldoff", new HashSet<>(shieldOff)).apply();
                toast(v ? "Shield on" : "Shield paused for " + host);
                if (current != null) current.web.reload();
            });
            boolean https = current.url != null && current.url.startsWith("https://");
            TextView conn = UI.text(this, https ? "Connection is encrypted (https)" : "Connection is NOT encrypted", 13, https ? UI.OK : UI.DANGER, false);
            conn.setPadding(dp(18), dp(4), dp(18), dp(8));
            list.addView(conn);
        }
        settingHeader(list, "Protection");
        settingSwitch(list, "Block ads & trackers", "Known ad and tracking servers (third-party only)", adBlock, v -> { adBlock = v; putBool("adblock", v); });
        settingSwitch(list, "Smart YouTube ad blocking", "Removes the ad schedule from the video data, hides ad boxes. Light on battery, no lag", ytShield, v -> { ytShield = v; putBool("ytshield", v); });
        settingSwitch(list, "Remove tracking from links", "utm_*, fbclid, gclid ...", stripLinks, v -> { stripLinks = v; putBool("striplinks", v); });
        settingSwitch(list, "Allow third-party cookies", "Off = websites cannot follow you across sites", thirdPartyCookies, v -> { thirdPartyCookies = v; putBool("thirdcookies", v); applyAllTabs(); });
        settingSwitch(list, "Safe Browsing", "Warn about dangerous sites", safeBrowsing, v -> { safeBrowsing = v; putBool("safebrowsing", v); applyAllTabs(); });
        settingSwitch(list, "Block screenshots", "Also hides the app in recent apps", blockShots, v -> { blockShots = v; putBool("blockshots", v); applySecure(); });
        settingLink(list, "lock", "Sites with the shield paused", shieldOff.size() + " sites", this::manageShieldOff);
        settingLink(list, "lock", "Site permissions", "Camera, microphone, location, DRM ...", this::manageSitePermissions);
        settingLink(list, "trash", "Clear browsing data", "Cookies, cache, history", this::clearData);
        TextView note = UI.text(this, "Pages always load over https. Camera, microphone and location are only used after you allow them for a site.", 12, UI.TEXT2, false);
        note.setPadding(dp(18), dp(16), dp(18), 0);
        list.addView(note);
        ScrollView sv = new ScrollView(this);
        sv.addView(list);
        root2.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        push(root2);
    }

    private void manageShieldOff() {
        if (shieldOff.isEmpty()) { toast("No sites in this list"); return; }
        final String[] hosts = shieldOff.toArray(new String[0]);
        final boolean[] on = new boolean[hosts.length];
        new AlertDialog.Builder(this).setTitle("Select sites to protect again")
                .setMultiChoiceItems(hosts, on, (dd, which, checked) -> on[which] = checked)
                .setPositiveButton("Protect", (dd, w) -> {
                    for (int i = 0; i < hosts.length; i++) if (on[i]) shieldOff.remove(hosts[i]);
                    prefs.edit().putStringSet("shieldoff", new HashSet<>(shieldOff)).apply();
                }).setNegativeButton("Cancel", null).show();
    }

    // ───────────────────────────── app lock ─────────────────────────────
    private void maybeLock() {
        if (!appLock || lockOverlay != null) return;
        KeyguardManager km = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        if (km == null || !km.isDeviceSecure()) return;
        boolean away = leftAt > 0 && System.currentTimeMillis() - leftAt > 30000;
        if (!lockPending && !away) return;
        lockPending = true;
        FrameLayout o = new FrameLayout(this);
        o.setBackgroundColor(UI.BG);
        o.setClickable(true);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER);
        ImageView ic = new ImageView(this);
        ic.setImageDrawable(Ico.of("lock", UI.ACCENT));
        col.addView(ic, new LinearLayout.LayoutParams(dp(56), dp(56)));
        TextView t = UI.text(this, "SPS Browser is locked", 20, UI.TEXT, true);
        t.setPadding(0, dp(14), 0, dp(18));
        col.addView(t);
        TextView b = UI.button(this, "Unlock", true);
        b.setOnClickListener(v -> askAppUnlock());
        col.addView(b);
        o.addView(col, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER));
        lockOverlay = o;
        root.addView(o, UI.match());
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE);
        askAppUnlock();
    }

    @SuppressWarnings("deprecation")
    private void askAppUnlock() {
        KeyguardManager km = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        if (km == null) { removeLock(); return; }
        Intent i = km.createConfirmDeviceCredentialIntent("SPS Browser", "Unlock SPS Browser");
        if (i == null) { removeLock(); return; }
        try { startActivityForResult(i, REQ_APPLOCK); } catch (Exception e) { removeLock(); }
    }

    private void removeLock() {
        if (lockOverlay != null) { root.removeView(lockOverlay); lockOverlay = null; }
        lockPending = false;
        applySecure();
    }

    // ───────────────────────────── life cycle ─────────────────────────────
    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQ_AUTH) {
            Runnable r = pendingUnlock;
            pendingUnlock = null;
            if (resultCode == RESULT_OK) { unlockedAt = System.currentTimeMillis(); if (r != null) r.run(); }
            else toast("Screen lock not confirmed");
            return;
        }
        if (requestCode == REQ_LENS) { onLensPicked(resultCode, data); return; }
        if (requestCode == REQ_APPLOCK) {
            if (resultCode == RESULT_OK) { lockPending = false; unlockedAt = System.currentTimeMillis(); removeLock(); }
            return;
        }
        if (requestCode == FILE_CHOOSER) {
            onFileChosen(resultCode, data);
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
        handleCommand(intent);
    }

    /** Buttons of the home-screen search widget. */
    private void handleCommand(Intent intent) {
        if (intent == null) return;
        String cmd = intent.getStringExtra(SearchWidget.CMD);
        if (cmd == null) return;
        intent.removeExtra(SearchWidget.CMD);
        if (lockOverlay != null) return;                       // locked: nothing starts before the unlock
        if (cmd.equals(SearchWidget.VOICE)) voiceSearch();
        else if (cmd.equals(SearchWidget.LENS)) startLens();
        else {
            if (current != null && !isNewTab(current.url)) newTab(null, current.priv, true);
            urlBar.requestFocus();
            InputMethodManager imm = (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
            if (imm != null) imm.showSoftInput(urlBar, InputMethodManager.SHOW_IMPLICIT);
        }
    }

    @Override
    public void onBackPressed() {
        if (!pages.isEmpty()) {
            View top = pages.get(pages.size() - 1);
            if (top instanceof Page && ((Page) top).onBack()) return;
            pop();
            return;
        }
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
        unlockedAt = 0;                                         // saved passwords lock again when the app goes to the background
        leftAt = System.currentTimeMillis();
        long delta = blockedCount.get() - blockedSaved;
        if (delta > 0) { blockedTotal += delta; blockedSaved = blockedCount.get(); prefs.edit().putLong("blocked_total", blockedTotal).apply(); }
        for (BTab t : tabs) captureThumb(t == current ? t : null);
        saveSession();
        for (BTab t : tabs) t.web.onPause();
        CookieManager.getInstance().flush();
    }

    @Override
    protected void onResume() {
        super.onResume();
        maybeLock();
        maybeShowDailyQuote();
        if (autoUpdate) checkForUpdate(false);
        for (BTab t : tabs) t.web.onResume();
    }

    @Override
    protected void onDestroy() {
        if (tts != null) { try { tts.stop(); tts.shutdown(); } catch (Exception ignored) { } tts = null; }
        if (clearOnExit && isFinishing() && !switchingProfile) clearAllDataNow();
        for (BTab t : new ArrayList<>(tabs)) {
            webHolder.removeView(t.web);
            t.web.destroy();
        }
        tabs.clear();
        super.onDestroy();
    }
}
