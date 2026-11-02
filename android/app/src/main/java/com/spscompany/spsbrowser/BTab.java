package com.spscompany.spsbrowser;

import android.graphics.Bitmap;
import android.webkit.WebView;

/** One browser tab. */
final class BTab {
    WebView web;
    boolean priv;
    boolean desktop;
    boolean pinned;
    boolean loading;
    String title = "New tab";
    String url = "";
    String mobileUa;
    Bitmap thumb;
    long lastUsed = System.currentTimeMillis();
}
