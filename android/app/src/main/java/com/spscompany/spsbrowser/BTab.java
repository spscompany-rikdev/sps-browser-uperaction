package com.spscompany.spsbrowser;

import android.graphics.Bitmap;
import android.webkit.WebView;

/** One browser tab. */
final class BTab {
    WebView web;
    boolean priv;
    boolean desktop;
    boolean pinned;
    String group;                // tab group name (null = not in a group)
    boolean loading;
    String title = "New tab";
    String url = "";
    String mobileUa;
    Bitmap thumb;
    long lastUsed = System.currentTimeMillis();
}
