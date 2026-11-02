package com.spscompany.spsbrowser;

import android.app.AlertDialog;
import android.app.Dialog;
import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Tab manager: thumbnail grid or list, normal / private switch, search, pin, duplicate, multi-select (close, pin, bookmark, share),
 * close duplicates, close all, sort, recently closed.
 */
final class TabsPage extends LinearLayout implements Page {
    interface Ops {
        List<BTab> tabs();
        BTab current();
        void switchTo(BTab t);
        void close(BTab t);
        BTab newTab(String url, boolean priv);
        void captureThumb(BTab t);
        void sortByTitle();
        List<String[]> recentlyClosed();
        void reopen(String[] entry);
    }

    private final Host host;
    private final Ops ops;
    private final Context c;
    private final LinearLayout header, searchRow, bottom;
    private final ScrollView scroll;
    private final LinearLayout content;
    private boolean showPrivate, grid = true, selecting, searching;
    private String query = "";
    private final Set<BTab> selected = new HashSet<>();
    private EditText searchBox;

    TabsPage(Host h, Ops o) {
        super(h.act());
        host = h; ops = o; c = h.act();
        setOrientation(VERTICAL);
        setBackgroundColor(UI.SURFACE);
        setClickable(true);
        BTab cur = o.current();
        showPrivate = cur != null && cur.priv;
        try { o.captureThumb(cur); } catch (Throwable ignored) { }

        header = new LinearLayout(c);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setBackgroundColor(UI.BG);
        header.setPadding(UI.dp(c, 4), 0, UI.dp(c, 4), 0);
        addView(header, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, UI.dp(c, 56)));
        searchRow = new LinearLayout(c);
        searchRow.setBackgroundColor(UI.BG);
        searchRow.setPadding(UI.dp(c, 12), 0, UI.dp(c, 12), UI.dp(c, 8));
        searchRow.setVisibility(GONE);
        addView(searchRow);
        addView(UI.divider(c));
        scroll = new ScrollView(c);
        content = new LinearLayout(c);
        content.setOrientation(VERTICAL);
        content.setPadding(UI.dp(c, 10), UI.dp(c, 10), UI.dp(c, 10), UI.dp(c, 90));
        scroll.addView(content);
        addView(scroll, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        addView(UI.divider(c));
        bottom = new LinearLayout(c);
        bottom.setGravity(Gravity.CENTER);
        bottom.setBackgroundColor(UI.BG);
        bottom.setPadding(UI.dp(c, 8), UI.dp(c, 8), UI.dp(c, 8), UI.dp(c, 8));
        addView(bottom, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        render();
    }

    private int count(boolean priv) {
        int n = 0;
        for (BTab t : ops.tabs()) if (t.priv == priv) n++;
        return n;
    }

    private List<BTab> visible() {
        List<BTab> l = new ArrayList<>();
        String q = query.trim().toLowerCase();
        for (BTab t : ops.tabs()) {
            if (t.priv != showPrivate) continue;
            if (!q.isEmpty() && !(t.title.toLowerCase().contains(q) || t.url.toLowerCase().contains(q))) continue;
            l.add(t);
        }
        List<BTab> sorted = new ArrayList<>();
        for (BTab t : l) if (t.pinned) sorted.add(t);
        for (BTab t : l) if (!t.pinned) sorted.add(t);
        return sorted;
    }

    // ───────────── drawing ─────────────
    private void render() {
        selected.retainAll(ops.tabs());
        if (selecting && selected.isEmpty()) selecting = false;
        buildHeader();
        buildBottom();
        content.removeAllViews();
        List<BTab> tabs = visible();
        if (tabs.isEmpty()) {
            TextView t = UI.text(c, query.isEmpty() ? (showPrivate ? "No private tabs" : "No tabs") : "No tabs match \"" + query + "\"", 15, UI.TEXT2, false);
            t.setGravity(Gravity.CENTER);
            t.setPadding(0, UI.dp(c, 80), 0, 0);
            content.addView(t);
            return;
        }
        boolean hasPinned = false;
        for (BTab t : tabs) if (t.pinned) hasPinned = true;
        if (grid) {
            DisplayMetrics dm = c.getResources().getDisplayMetrics();
            int cardW = (dm.widthPixels - UI.dp(c, 10 * 2 + 10)) / 2;
            LinearLayout rowL = null;
            for (int i = 0; i < tabs.size(); i++) {
                if (i % 2 == 0) {
                    rowL = new LinearLayout(c);
                    LayoutParams rp = new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                    rp.bottomMargin = UI.dp(c, 10);
                    content.addView(rowL, rp);
                }
                View card = gridCard(tabs.get(i), cardW);
                LayoutParams cp = new LayoutParams(cardW, UI.dp(c, 200));
                if (i % 2 == 0) cp.rightMargin = UI.dp(c, 10);
                rowL.addView(card, cp);
            }
        } else {
            for (BTab t : tabs) {
                View r = listRow(t);
                LayoutParams lp = new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                lp.bottomMargin = UI.dp(c, 8);
                content.addView(r, lp);
            }
        }
    }

    private void buildHeader() {
        header.removeAllViews();
        if (selecting) {
            ImageView x = UI.icon(c, "close", UI.TEXT, 44, 11);
            x.setOnClickListener(v -> { selecting = false; selected.clear(); render(); });
            header.addView(x);
            header.addView(UI.text(c, selected.size() + " selected", 17, UI.TEXT, true), new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            ImageView all = UI.icon(c, "check", UI.ACCENT, 44, 11);
            all.setContentDescription("Select all");
            all.setOnClickListener(v -> {
                List<BTab> vis = visible();
                if (selected.containsAll(vis)) selected.clear(); else selected.addAll(vis);
                if (selected.isEmpty()) selecting = false;
                render();
            });
            header.addView(all);
            return;
        }
        ImageView back = UI.icon(c, "back", UI.TEXT, 44, 11);
        back.setOnClickListener(v -> host.pop());
        header.addView(back);
        header.addView(segment("Tabs " + count(false), !showPrivate, false), new LayoutParams(0, UI.dp(c, 36), 1f));
        header.addView(UI.space(c, 8, 1));
        header.addView(segment("Private " + count(true), showPrivate, true), new LayoutParams(0, UI.dp(c, 36), 1f));
        ImageView s = UI.icon(c, "search", UI.TEXT, 44, 11);
        s.setOnClickListener(v -> toggleSearch());
        header.addView(s);
        ImageView g = UI.icon(c, grid ? "list" : "grid", UI.TEXT, 44, 11);
        g.setContentDescription("Switch view");
        g.setOnClickListener(v -> { grid = !grid; render(); });
        header.addView(g);
        ImageView m = UI.icon(c, "menu", UI.TEXT, 44, 11);
        m.setOnClickListener(v -> menu());
        header.addView(m);
    }

    private View segment(String label, boolean on, final boolean priv) {
        TextView t = UI.text(c, label, 13, on ? (priv ? UI.PRIVATE : UI.ACCENT) : UI.TEXT2, true);
        t.setGravity(Gravity.CENTER);
        t.setBackground(UI.ripple(c, on ? (priv ? UI.PRIVATE_BG : UI.ACCENT_BG) : UI.SURFACE, 18, 0));
        t.setOnClickListener(v -> { showPrivate = priv; selected.clear(); selecting = false; render(); });
        return t;
    }

    private void buildBottom() {
        bottom.removeAllViews();
        if (selecting) {
            bottom.addView(action("Close", "trash", UI.DANGER, v -> {
                for (BTab t : new ArrayList<>(selected)) if (!t.pinned || true) ops.close(t);
                selected.clear(); selecting = false; render();
            }));
            bottom.addView(action("Pin", "pin", UI.TEXT, v -> {
                boolean allPinned = true;
                for (BTab t : selected) if (!t.pinned) allPinned = false;
                for (BTab t : selected) t.pinned = !allPinned;
                selected.clear(); selecting = false; render();
            }));
            bottom.addView(action("Bookmark", "star", UI.TEXT, v -> {
                int n = 0;
                for (BTab t : selected) if (!t.priv && t.url.startsWith("http")) { host.store().addBookmark(t.title, t.url); n++; }
                host.toast(n + " bookmarked");
                selected.clear(); selecting = false; render();
            }));
            bottom.addView(action("Share", "share", UI.TEXT, v -> {
                StringBuilder sb = new StringBuilder();
                for (BTab t : selected) if (t.url.startsWith("http")) sb.append(t.title).append("\n").append(t.url).append("\n\n");
                host.share(sb.toString().trim());
            }));
            bottom.addView(action("Duplicate", "copy", UI.TEXT, v -> {
                for (BTab t : new ArrayList<>(selected)) if (t.url.startsWith("http")) ops.newTab(t.url, t.priv);
                selected.clear(); selecting = false; render();
            }));
            return;
        }
        TextView add = UI.button(c, showPrivate ? "+  New private tab" : "+  New tab", true);
        if (showPrivate) add.setBackground(UI.ripple(c, UI.PRIVATE, 20, 0));
        add.setOnClickListener(v -> { ops.newTab(null, showPrivate); host.pop(); });
        bottom.addView(add);
    }

    private View action(String label, String icon, int tint, OnClickListener l) {
        LinearLayout b = new LinearLayout(c);
        b.setOrientation(VERTICAL);
        b.setGravity(Gravity.CENTER);
        b.setBackground(UI.ripple(c, Color.TRANSPARENT, 8, 0));
        b.setPadding(UI.dp(c, 6), UI.dp(c, 4), UI.dp(c, 6), UI.dp(c, 4));
        ImageView i = new ImageView(c);
        i.setImageDrawable(Ico.of(icon, tint));
        b.addView(i, new LayoutParams(UI.dp(c, 22), UI.dp(c, 22)));
        b.addView(UI.text(c, label, 11, tint, false));
        b.setOnClickListener(l);
        LayoutParams lp = new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        b.setLayoutParams(lp);
        return b;
    }

    private View gridCard(final BTab t, int w) {
        FrameLayout card = new FrameLayout(c);
        boolean isCur = t == ops.current();
        boolean sel = selected.contains(t);
        card.setBackground(UI.box(c, UI.BG, 12, sel || isCur ? (t.priv ? UI.PRIVATE : UI.ACCENT) : UI.BORDER));
        card.setClipToOutline(true);
        LinearLayout col = new LinearLayout(c);
        col.setOrientation(VERTICAL);
        LinearLayout top = new LinearLayout(c);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(UI.dp(c, 8), 0, UI.dp(c, 2), 0);
        top.addView(UI.avatar(c, UI.hostOf(t.url).isEmpty() ? "N" : UI.hostOf(t.url), t.priv ? UI.PRIVATE : UI.colorFor(UI.hostOf(t.url)), 20));
        TextView title = UI.oneLine(c, titleOf(t), 12, UI.TEXT, true);
        title.setPadding(UI.dp(c, 8), 0, 0, 0);
        top.addView(title, new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        if (!selecting) {
            ImageView x = UI.icon(c, "close", UI.TEXT2, 34, 9);
            x.setOnClickListener(v -> { ops.close(t); render(); });
            top.addView(x);
        }
        col.addView(top, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, UI.dp(c, 36)));
        col.addView(thumbView(t), new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        card.addView(col, UI.match());
        if (t.pinned) {
            ImageView pin = new ImageView(c);
            pin.setImageDrawable(Ico.of("pin", Color.WHITE));
            pin.setPadding(UI.dp(c, 4), UI.dp(c, 4), UI.dp(c, 4), UI.dp(c, 4));
            pin.setBackground(UI.box(c, 0xCC202124, 10, 0));
            FrameLayout.LayoutParams pp = new FrameLayout.LayoutParams(UI.dp(c, 20), UI.dp(c, 20), Gravity.BOTTOM | Gravity.START);
            pp.setMargins(UI.dp(c, 8), 0, 0, UI.dp(c, 8));
            card.addView(pin, pp);
        }
        if (selecting) {
            ImageView chk = new ImageView(c);
            chk.setImageDrawable(Ico.of("check", sel ? Color.WHITE : 0x00000000));
            int pad = UI.dp(c, 4);
            chk.setPadding(pad, pad, pad, pad);
            chk.setBackground(UI.box(c, sel ? UI.ACCENT : Color.WHITE, 12, sel ? UI.ACCENT : UI.TEXT3));
            FrameLayout.LayoutParams cp = new FrameLayout.LayoutParams(UI.dp(c, 24), UI.dp(c, 24), Gravity.TOP | Gravity.END);
            cp.setMargins(0, UI.dp(c, 6), UI.dp(c, 6), 0);
            card.addView(chk, cp);
        }
        wire(card, t);
        return card;
    }

    private View thumbView(BTab t) {
        FrameLayout f = new FrameLayout(c);
        f.setBackgroundColor(t.priv ? UI.PRIVATE_BG : UI.SURFACE);
        if (t.thumb != null && !t.priv) {
            ImageView iv = new ImageView(c);
            iv.setImageBitmap(t.thumb);
            iv.setScaleType(ImageView.ScaleType.MATRIX);
            f.addView(iv, UI.match());
            iv.post(() -> {                                   // show the top of the page, fitted to the card width
                if (iv.getWidth() <= 0 || t.thumb == null) return;
                float s = iv.getWidth() / (float) t.thumb.getWidth();
                android.graphics.Matrix m = new android.graphics.Matrix();
                m.setScale(s, s);
                iv.setImageMatrix(m);
            });
        } else {
            ImageView ic = new ImageView(c);
            ic.setImageDrawable(Ico.of(t.priv ? "incognito" : "globe", t.priv ? UI.PRIVATE : UI.TEXT3));
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(UI.dp(c, 40), UI.dp(c, 40), Gravity.CENTER);
            f.addView(ic, lp);
        }
        return f;
    }

    private View listRow(final BTab t) {
        LinearLayout r = new LinearLayout(c);
        r.setGravity(Gravity.CENTER_VERTICAL);
        boolean sel = selected.contains(t);
        r.setBackground(UI.box(c, sel ? UI.ACCENT_BG : UI.BG, 12, t == ops.current() ? (t.priv ? UI.PRIVATE : UI.ACCENT) : UI.BORDER));
        r.setPadding(UI.dp(c, 10), UI.dp(c, 8), UI.dp(c, 4), UI.dp(c, 8));
        FrameLayout th = new FrameLayout(c);
        th.setBackground(UI.box(c, UI.SURFACE, 8, 0));
        th.setClipToOutline(true);
        View tv = thumbView(t);
        th.addView(tv, UI.match());
        r.addView(th, new LayoutParams(UI.dp(c, 64), UI.dp(c, 46)));
        LinearLayout col = new LinearLayout(c);
        col.setOrientation(VERTICAL);
        col.setPadding(UI.dp(c, 12), 0, UI.dp(c, 6), 0);
        TextView title = UI.oneLine(c, (t.pinned ? "📌 " : "") + titleOf(t), 14, UI.TEXT, true);
        col.addView(title);
        col.addView(UI.oneLine(c, UI.hostOf(t.url), 12, UI.TEXT2, false));
        r.addView(col, new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        if (selecting) {
            ImageView chk = new ImageView(c);
            chk.setImageDrawable(Ico.of("check", sel ? Color.WHITE : 0x00000000));
            int pad = UI.dp(c, 4);
            chk.setPadding(pad, pad, pad, pad);
            chk.setBackground(UI.box(c, sel ? UI.ACCENT : Color.WHITE, 12, sel ? UI.ACCENT : UI.TEXT3));
            r.addView(chk, new LayoutParams(UI.dp(c, 24), UI.dp(c, 24)));
            r.addView(UI.space(c, 8, 1));
        } else {
            ImageView x = UI.icon(c, "close", UI.TEXT2, 40, 11);
            x.setOnClickListener(v -> { ops.close(t); render(); });
            r.addView(x);
        }
        wire(r, t);
        return r;
    }

    private String titleOf(BTab t) {
        if (t.title != null && !t.title.isEmpty()) return t.title;
        return t.url == null || t.url.isEmpty() ? "New tab" : t.url;
    }

    private void wire(View v, final BTab t) {
        v.setClickable(true);
        v.setOnClickListener(x -> {
            if (selecting) {
                if (!selected.remove(t)) selected.add(t);
                render();
            } else {
                ops.switchTo(t);
                host.pop();
            }
        });
        v.setOnLongClickListener(x -> {
            if (!selecting) { selecting = true; selected.add(t); render(); }
            else tabMenu(t);
            return true;
        });
    }

    // ───────────── menus ─────────────
    private void tabMenu(final BTab t) {
        LinearLayout box = new LinearLayout(c);
        box.setOrientation(VERTICAL);
        final Dialog[] d = new Dialog[1];
        addSheetRow(box, d, t.pinned ? "Unpin tab" : "Pin tab", "pin", () -> { t.pinned = !t.pinned; render(); });
        addSheetRow(box, d, "Duplicate", "copy", () -> { if (t.url.startsWith("http")) { ops.newTab(t.url, t.priv); render(); } });
        addSheetRow(box, d, "Copy link", "copy", () -> host.copySecret(t.url));
        addSheetRow(box, d, "Close other tabs", "close", () -> { for (BTab o : new ArrayList<>(ops.tabs())) if (o != t && !o.pinned) ops.close(o); render(); });
        d[0] = UI.sheet(host.act(), box);
        d[0].show();
    }

    private void menu() {
        LinearLayout box = new LinearLayout(c);
        box.setOrientation(VERTICAL);
        box.setPadding(0, 0, 0, UI.dp(c, 12));
        final Dialog[] d = new Dialog[1];
        addSheetRow(box, d, "Select tabs", "check", () -> { selecting = true; selected.clear(); render(); host.toast("Tap tabs to select them"); });
        addSheetRow(box, d, "Sort A to Z", "list", () -> { ops.sortByTitle(); render(); });
        addSheetRow(box, d, "Close duplicate tabs", "copy", this::closeDuplicates);
        addSheetRow(box, d, "Recently closed", "history", this::recentlyClosed);
        addSheetRow(box, d, "Bookmark all tabs", "star", () -> {
            int n = 0;
            for (BTab t : visible()) if (!t.priv && t.url.startsWith("http")) { host.store().addBookmark(t.title, t.url); n++; }
            host.toast(n + " tabs bookmarked");
        });
        addSheetRow(box, d, "Share all links", "share", () -> {
            StringBuilder sb = new StringBuilder();
            for (BTab t : visible()) if (t.url.startsWith("http")) sb.append(t.title).append("\n").append(t.url).append("\n\n");
            host.share(sb.toString().trim());
        });
        LinearLayout danger = UI.row(c, "trash", showPrivate ? "Close all private tabs" : "Close all tabs (pinned stay)", null, UI.DANGER);
        ((TextView) ((LinearLayout) danger.getChildAt(2)).getChildAt(0)).setTextColor(UI.DANGER);
        danger.setOnClickListener(v -> { d[0].dismiss(); closeAll(); });
        box.addView(danger);
        d[0] = UI.sheet(host.act(), box);
        d[0].show();
    }

    private void addSheetRow(LinearLayout box, final Dialog[] d, String label, String icon, final Runnable r) {
        LinearLayout row = UI.row(c, icon, label, null, UI.TEXT);
        row.setOnClickListener(v -> { d[0].dismiss(); r.run(); });
        box.addView(row);
    }

    private void closeAll() {
        final List<BTab> victims = new ArrayList<>();
        for (BTab t : ops.tabs()) if (t.priv == showPrivate && !t.pinned) victims.add(t);
        if (victims.isEmpty()) { host.toast("Nothing to close"); return; }
        new AlertDialog.Builder(host.act()).setMessage("Close " + victims.size() + " tabs?")
                .setPositiveButton("Close", (dd, w) -> { for (BTab t : victims) ops.close(t); render(); })
                .setNegativeButton("Cancel", null).show();
    }

    private void closeDuplicates() {
        Set<String> seen = new HashSet<>();
        int n = 0;
        for (BTab t : new ArrayList<>(ops.tabs())) {
            if (t.priv != showPrivate || t.url == null || !t.url.startsWith("http")) continue;
            if (!seen.add(t.url) && !t.pinned && t != ops.current()) { ops.close(t); n++; }
        }
        host.toast(n == 0 ? "No duplicate tabs" : n + " duplicate tabs closed");
        render();
    }

    private void recentlyClosed() {
        final List<String[]> rc = ops.recentlyClosed();
        ListPage lp = new ListPage(host, "Recently closed", () -> {
            List<ListPage.Item> items = new ArrayList<>();
            List<String[]> now = ops.recentlyClosed();
            for (int i = now.size() - 1; i >= 0; i--) {
                ListPage.Item it = new ListPage.Item();
                it.id = String.valueOf(i);
                it.title = now.get(i)[0];
                it.sub = UI.hostOf(now.get(i)[1]);
                it.tag = now.get(i);
                items.add(it);
            }
            return items;
        }, it -> { ops.reopen((String[]) it.tag); host.pop(); host.pop(); }).empty("No recently closed tabs", "history");
        host.push(lp);
    }

    // ───────────── search ─────────────
    private void toggleSearch() {
        searching = !searching;
        searchRow.removeAllViews();
        if (!searching) {
            query = "";
            searchRow.setVisibility(GONE);
            render();
            return;
        }
        searchRow.setVisibility(VISIBLE);
        searchBox = UI.field(c, "Search open tabs", false);
        searchBox.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int d) { }
            @Override public void onTextChanged(CharSequence s, int a, int b, int d) { query = s.toString(); render(); }
            @Override public void afterTextChanged(Editable s) { }
        });
        searchRow.addView(searchBox, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, UI.dp(c, 40)));
        searchBox.requestFocus();
    }

    @Override
    public boolean onBack() {
        if (selecting) { selecting = false; selected.clear(); render(); return true; }
        if (searching) { toggleSearch(); return true; }
        return false;
    }
}
