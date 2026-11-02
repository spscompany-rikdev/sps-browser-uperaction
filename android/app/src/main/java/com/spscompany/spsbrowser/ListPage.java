package com.spscompany.spsbrowser;

import android.app.Activity;
import android.app.Dialog;
import android.content.Context;
import android.graphics.Color;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.widget.BaseAdapter;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ProgressBar;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * One full-screen list used for Bookmarks, History, Downloads and Passwords: search, long-press to select several items,
 * select all, bulk actions, sections, optional live refresh.
 */
final class ListPage extends LinearLayout implements Page {
    static final class Item {
        String id, title = "", sub = "", trailing = "", section = "", letter = "", icon;
        int color, progress = -1;
        boolean selected, warn;
        Object tag;
    }

    interface Source { List<Item> load(); }
    interface OnOpen { void open(Item it); }
    interface Run { void run(List<Item> selected); }

    private static final class Act {
        String label, icon;
        Run run;
        boolean danger;
    }

    private final Host host;
    private final Context c;
    private final Source source;
    private final OnOpen onOpen;
    private final String title;
    private final List<Act> bulk = new ArrayList<>();
    private final List<Act> menu = new ArrayList<>();
    private final List<Item> all = new ArrayList<>();
    private final List<Item> shown = new ArrayList<>();
    private final LinearLayout header;
    private final ListView list;
    private final TextView emptyView;
    private final BaseAdapter adapter;
    private EditText searchBox;
    private boolean searching, selecting, searchable = true;
    private String query = "";
    private String emptyText = "Nothing here yet";
    private String emptyIcon = "info";
    private long liveMs;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable ticker = new Runnable() {
        @Override public void run() {
            if (!isAttachedToWindow()) return;
            if (!selecting) refresh();
            handler.postDelayed(this, liveMs);
        }
    };
    private static final int MAX_SHOWN = 400;
    private boolean showAll;

    ListPage(Host h, String title, Source src, OnOpen open) {
        super(h.act());
        host = h; c = h.act(); source = src; onOpen = open; this.title = title;
        setOrientation(VERTICAL);
        setBackgroundColor(UI.BG);
        setClickable(true);
        header = new LinearLayout(c);
        header.setOrientation(HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(UI.dp(c, 4), 0, UI.dp(c, 4), 0);
        addView(header, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, UI.dp(c, 56)));
        addView(UI.divider(c));

        FrameLayout body = new FrameLayout(c);
        list = new ListView(c);
        list.setDivider(null);
        list.setVerticalScrollBarEnabled(false);
        emptyView = UI.text(c, emptyText, 15, UI.TEXT2, false);
        emptyView.setGravity(Gravity.CENTER);
        body.addView(list, UI.match());
        FrameLayout.LayoutParams ep = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.CENTER);
        body.addView(emptyView, ep);
        addView(body, new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        adapter = new BaseAdapter() {
            @Override public int getCount() { return shown.size() + (all.size() > MAX_SHOWN && !showAll && query.isEmpty() ? 1 : 0); }
            @Override public Object getItem(int i) { return i < shown.size() ? shown.get(i) : null; }
            @Override public long getItemId(int i) { return i; }
            @Override public int getViewTypeCount() { return 3; }
            @Override public int getItemViewType(int i) {
                if (i >= shown.size()) return 2;
                return shown.get(i).id == null ? 1 : 0;
            }
            @Override public View getView(int i, View v, ViewGroup p) {
                if (i >= shown.size()) return moreRow();
                Item it = shown.get(i);
                return it.id == null ? sectionRow(it) : itemRow(it);
            }
        };
        list.setAdapter(adapter);
        list.setOnItemClickListener((p, v, pos, id) -> {
            if (pos >= shown.size()) { showAll = true; applyFilter(); return; }
            Item it = shown.get(pos);
            if (it.id == null) return;
            if (selecting) { it.selected = !it.selected; refreshHeader(); adapter.notifyDataSetChanged(); if (selectedCount() == 0) endSelect(); }
            else if (onOpen != null) onOpen.open(it);
        });
        list.setOnItemLongClickListener((p, v, pos, id) -> {
            if (pos >= shown.size()) return true;
            Item it = shown.get(pos);
            if (it.id == null) return true;
            selecting = true;
            it.selected = true;
            refreshHeader();
            adapter.notifyDataSetChanged();
            return true;
        });
        refresh();
        refreshHeader();
    }

    // ───────────── configuration ─────────────
    ListPage bulk(String label, String icon, boolean danger, Run r) { Act a = new Act(); a.label = label; a.icon = icon; a.run = r; a.danger = danger; bulk.add(a); return this; }
    ListPage menu(String label, boolean danger, Run r) { Act a = new Act(); a.label = label; a.run = r; a.danger = danger; menu.add(a); refreshHeader(); return this; }
    ListPage searchable(boolean s) { searchable = s; refreshHeader(); return this; }
    ListPage empty(String text, String icon) { emptyText = text; emptyIcon = icon; emptyView.setText(text); updateEmpty(); return this; }
    ListPage live(long ms) { liveMs = ms; handler.removeCallbacks(ticker); handler.postDelayed(ticker, ms); return this; }

    @Override
    protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        if (liveMs > 0) { handler.removeCallbacks(ticker); handler.postDelayed(ticker, liveMs); }
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        handler.removeCallbacks(ticker);
    }

    // ───────────── data ─────────────
    void refresh() {
        List<Item> fresh = source.load();
        java.util.HashSet<String> sel = new java.util.HashSet<>();
        for (Item it : all) if (it.selected && it.id != null) sel.add(it.id);
        all.clear();
        all.addAll(fresh);
        for (Item it : all) if (it.id != null && sel.contains(it.id)) it.selected = true;
        applyFilter();
        refreshHeader();
    }

    private void applyFilter() {
        shown.clear();
        String q = query.trim().toLowerCase();
        String lastSection = null;
        int count = 0;
        for (Item it : all) {
            if (it.id == null) continue;
            if (!q.isEmpty() && !(it.title.toLowerCase().contains(q) || it.sub.toLowerCase().contains(q))) continue;
            if (!showAll && q.isEmpty() && ++count > MAX_SHOWN) break;
            if (it.section != null && !it.section.isEmpty() && !it.section.equals(lastSection)) {
                Item s = new Item();
                s.title = it.section;
                shown.add(s);
                lastSection = it.section;
            }
            shown.add(it);
        }
        adapter.notifyDataSetChanged();
        updateEmpty();
    }

    private void updateEmpty() {
        boolean none = shown.isEmpty();
        emptyView.setVisibility(none ? VISIBLE : GONE);
        emptyView.setText(query.isEmpty() ? emptyText : "No results for \"" + query + "\"");
        emptyView.setCompoundDrawablePadding(UI.dp(c, 10));
        emptyView.setCompoundDrawablesWithIntrinsicBounds(null, Ico.of(emptyIcon, UI.TEXT3), null, null);
        android.graphics.drawable.Drawable d = emptyView.getCompoundDrawables()[1];
        if (d != null) d.setBounds(0, 0, UI.dp(c, 48), UI.dp(c, 48));
        emptyView.setCompoundDrawables(null, d, null, null);
    }

    private int selectedCount() {
        int n = 0;
        for (Item it : all) if (it.selected) n++;
        return n;
    }

    private List<Item> selectedItems() {
        List<Item> l = new ArrayList<>();
        for (Item it : all) if (it.selected && it.id != null) l.add(it);
        return l;
    }

    private void endSelect() {
        selecting = false;
        for (Item it : all) it.selected = false;
        refreshHeader();
        adapter.notifyDataSetChanged();
    }

    // ───────────── header ─────────────
    private void refreshHeader() {
        header.removeAllViews();
        if (selecting) {
            ImageView x = UI.icon(c, "close", UI.TEXT, 44, 11);
            x.setOnClickListener(v -> endSelect());
            header.addView(x);
            TextView t = UI.text(c, selectedCount() + " selected", 17, UI.TEXT, true);
            header.addView(t, new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            ImageView all = UI.icon(c, "check", UI.ACCENT, 44, 11);
            all.setContentDescription("Select all");
            all.setOnClickListener(v -> {
                boolean every = selectedCount() >= visibleItemCount();
                for (Item it : this.all) if (it.id != null && matches(it)) it.selected = !every;
                if (selectedCount() == 0) endSelect(); else { refreshHeader(); adapter.notifyDataSetChanged(); }
            });
            header.addView(all);
            int shownIcons = 0;
            final List<Act> overflow = new ArrayList<>();
            for (Act a : bulk) {
                if (shownIcons < 3 && a.icon != null) {
                    final Act aa = a;
                    ImageView b = UI.icon(c, a.icon, a.danger ? UI.DANGER : UI.TEXT, 44, 11);
                    b.setContentDescription(a.label);
                    b.setOnClickListener(v -> runBulk(aa));
                    header.addView(b);
                    shownIcons++;
                } else overflow.add(a);
            }
            if (!overflow.isEmpty()) {
                ImageView m = UI.icon(c, "menu", UI.TEXT, 44, 11);
                m.setOnClickListener(v -> sheetOf(overflow, true));
                header.addView(m);
            }
            return;
        }
        ImageView back = UI.icon(c, "back", UI.TEXT, 44, 11);
        back.setOnClickListener(v -> host.pop());
        header.addView(back);
        if (searching) {
            searchBox = UI.field(c, "Search " + title.toLowerCase(), false);
            searchBox.setText(query);
            searchBox.setSelection(query.length());
            searchBox.addTextChangedListener(new TextWatcher() {
                @Override public void beforeTextChanged(CharSequence s, int a, int b, int d) { }
                @Override public void onTextChanged(CharSequence s, int a, int b, int d) { query = s.toString(); applyFilter(); }
                @Override public void afterTextChanged(Editable s) { }
            });
            header.addView(searchBox, new LayoutParams(0, UI.dp(c, 40), 1f));
            ImageView x = UI.icon(c, "close", UI.TEXT2, 44, 11);
            x.setOnClickListener(v -> stopSearch());
            header.addView(x);
            searchBox.post(() -> {
                searchBox.requestFocus();
                InputMethodManager imm = (InputMethodManager) c.getSystemService(Context.INPUT_METHOD_SERVICE);
                if (imm != null) imm.showSoftInput(searchBox, 0);
            });
            return;
        }
        TextView t = UI.text(c, title, 19, UI.TEXT, true);
        t.setPadding(UI.dp(c, 4), 0, 0, 0);
        header.addView(t, new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        if (searchable) {
            ImageView s = UI.icon(c, "search", UI.TEXT, 44, 11);
            s.setOnClickListener(v -> { searching = true; refreshHeader(); });
            header.addView(s);
        }
        if (!menu.isEmpty()) {
            ImageView m = UI.icon(c, "menu", UI.TEXT, 44, 11);
            m.setOnClickListener(v -> sheetOf(menu, false));
            header.addView(m);
        }
    }

    private boolean matches(Item it) {
        String q = query.trim().toLowerCase();
        return q.isEmpty() || it.title.toLowerCase().contains(q) || it.sub.toLowerCase().contains(q);
    }

    private int visibleItemCount() {
        int n = 0;
        for (Item it : all) if (it.id != null && matches(it)) n++;
        return n;
    }

    private void stopSearch() {
        searching = false;
        query = "";
        InputMethodManager imm = (InputMethodManager) c.getSystemService(Context.INPUT_METHOD_SERVICE);
        if (imm != null && searchBox != null) imm.hideSoftInputFromWindow(searchBox.getWindowToken(), 0);
        applyFilter();
        refreshHeader();
    }

    private void runBulk(Act a) {
        List<Item> sel = selectedItems();
        if (sel.isEmpty()) return;
        a.run.run(sel);
        endSelect();
        refresh();
    }

    private void sheetOf(final List<Act> acts, final boolean needsSelection) {
        LinearLayout box = new LinearLayout(c);
        box.setOrientation(VERTICAL);
        box.setPadding(0, 0, 0, UI.dp(c, 12));
        final Dialog[] dlg = new Dialog[1];
        for (final Act a : acts) {
            LinearLayout r = UI.row(c, a.icon, a.label, null, a.danger ? UI.DANGER : UI.TEXT);
            r.setOnClickListener(v -> {
                dlg[0].dismiss();
                if (needsSelection) runBulk(a); else { a.run.run(new ArrayList<Item>()); refresh(); }
            });
            ((TextView) ((LinearLayout) r.getChildAt(r.getChildCount() - 1)).getChildAt(0)).setTextColor(a.danger ? UI.DANGER : UI.TEXT);
            box.addView(r);
        }
        dlg[0] = UI.sheet(host.act(), box);
        dlg[0].show();
    }

    // ───────────── rows ─────────────
    private View sectionRow(Item it) {
        TextView t = UI.text(c, it.title, 13, UI.ACCENT, true);
        t.setPadding(UI.dp(c, 18), UI.dp(c, 16), UI.dp(c, 18), UI.dp(c, 6));
        return t;
    }

    private View moreRow() {
        TextView t = UI.text(c, "Show all " + all.size() + " items", 14, UI.ACCENT, true);
        t.setGravity(Gravity.CENTER);
        t.setPadding(0, UI.dp(c, 16), 0, UI.dp(c, 16));
        return t;
    }

    private View itemRow(Item it) {
        LinearLayout r = new LinearLayout(c);
        r.setOrientation(HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(UI.dp(c, 16), UI.dp(c, 10), UI.dp(c, 16), UI.dp(c, 10));
        r.setBackground(it.selected ? new android.graphics.drawable.ColorDrawable(UI.ACCENT_BG) : UI.ripple(c, Color.TRANSPARENT, 0, 0));
        View lead;
        if (selecting) {
            ImageView chk = new ImageView(c);
            chk.setImageDrawable(Ico.of("check", it.selected ? Color.WHITE : 0x00000000));
            int pad = UI.dp(c, 6);
            chk.setPadding(pad, pad, pad, pad);
            chk.setBackground(UI.box(c, it.selected ? UI.ACCENT : Color.WHITE, 16, it.selected ? UI.ACCENT : UI.TEXT3));
            lead = chk;
            r.addView(lead, new LayoutParams(UI.dp(c, 32), UI.dp(c, 32)));
        } else if (it.icon != null) {
            ImageView ic = new ImageView(c);
            ic.setImageDrawable(Ico.of(it.icon, it.color != 0 ? it.color : UI.TEXT2));
            int pad = UI.dp(c, 7);
            ic.setPadding(pad, pad, pad, pad);
            ic.setBackground(UI.box(c, UI.SURFACE, 16, 0));
            r.addView(ic, new LayoutParams(UI.dp(c, 32), UI.dp(c, 32)));
        } else {
            r.addView(UI.avatar(c, it.letter.isEmpty() ? it.title : it.letter, it.color != 0 ? it.color : UI.colorFor(it.title), 32));
        }
        r.addView(UI.space(c, 14, 1));
        LinearLayout col = new LinearLayout(c);
        col.setOrientation(VERTICAL);
        col.addView(UI.oneLine(c, it.title.isEmpty() ? "(no title)" : it.title, 15, it.warn ? UI.DANGER : UI.TEXT, false));
        if (!it.sub.isEmpty()) col.addView(UI.oneLine(c, it.sub, 12, UI.TEXT2, false));
        if (it.progress >= 0 && it.progress < 100) {
            ProgressBar pb = new ProgressBar(c, null, android.R.attr.progressBarStyleHorizontal);
            pb.setMax(100);
            pb.setProgress(it.progress);
            LayoutParams pp = new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, UI.dp(c, 4));
            pp.topMargin = UI.dp(c, 6);
            col.addView(pb, pp);
        }
        r.addView(col, new LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        if (!it.trailing.isEmpty()) {
            TextView tr = UI.text(c, it.trailing, 12, UI.TEXT3, false);
            tr.setPadding(UI.dp(c, 8), 0, 0, 0);
            r.addView(tr);
        }
        return r;
    }

    // ───────────── back ─────────────
    @Override
    public boolean onBack() {
        if (selecting) { endSelect(); return true; }
        if (searching) { stopSearch(); return true; }
        return false;
    }
}
