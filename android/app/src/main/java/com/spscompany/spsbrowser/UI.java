package com.spscompany.spsbrowser;

import android.app.Activity;
import android.app.Dialog;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Classic white design: colours and small view builders shared by every screen. */
final class UI {
    static final int BG = 0xFFFFFFFF;
    static final int SURFACE = 0xFFF6F7F9;
    static final int BORDER = 0xFFE3E6EA;
    static final int TEXT = 0xFF202124;
    static final int TEXT2 = 0xFF5F6368;
    static final int TEXT3 = 0xFF9AA0A6;
    static final int ACCENT = 0xFF1A73E8;
    static final int ACCENT_BG = 0xFFE8F0FE;
    static final int DANGER = 0xFFD93025;
    static final int OK = 0xFF188038;
    static final int PRIVATE = 0xFF5E35B1;
    static final int PRIVATE_BG = 0xFFEDE7F6;

    private UI() { }

    static int dp(Context c, float v) {
        return Math.round(v * c.getResources().getDisplayMetrics().density);
    }

    static GradientDrawable box(Context c, int fill, float radiusDp, int stroke) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(dp(c, radiusDp));
        if (stroke != 0) g.setStroke(Math.max(1, dp(c, 1)), stroke);
        return g;
    }

    static Drawable ripple(Context c, int fill, float radiusDp, int stroke) {
        return new RippleDrawable(ColorStateList.valueOf(0x22000000), box(c, fill, radiusDp, stroke), box(c, Color.WHITE, radiusDp, 0));
    }

    static TextView text(Context c, String s, float sp, int color, boolean bold) {
        TextView t = new TextView(c);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    static TextView oneLine(Context c, String s, float sp, int color, boolean bold) {
        TextView t = text(c, s, sp, color, bold);
        t.setSingleLine(true);
        t.setEllipsize(TextUtils.TruncateAt.END);
        return t;
    }

    /** Round icon button. */
    static ImageView icon(Context c, String name, int tint, int sizeDp, int padDp) {
        ImageView v = new ImageView(c);
        v.setImageDrawable(Ico.of(name, tint));
        int p = dp(c, padDp);
        v.setPadding(p, p, p, p);
        v.setScaleType(ImageView.ScaleType.FIT_CENTER);
        v.setBackground(ripple(c, Color.TRANSPARENT, sizeDp / 2f, 0));
        v.setLayoutParams(new LinearLayout.LayoutParams(dp(c, sizeDp), dp(c, sizeDp)));
        v.setClickable(true);
        v.setFocusable(true);
        v.setContentDescription(name);
        return v;
    }

    static void setIcon(ImageView v, String name, int tint) {
        v.setImageDrawable(Ico.of(name, tint));
    }

    static View divider(Context c) {
        View v = new View(c);
        v.setBackgroundColor(BORDER);
        v.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, Math.max(1, dp(c, 1))));
        return v;
    }

    static View space(Context c, int wDp, int hDp) {
        View v = new View(c);
        v.setLayoutParams(new LinearLayout.LayoutParams(dp(c, wDp), dp(c, hDp)));
        return v;
    }

    /** Coloured circle with a letter, used as the avatar for sites and profiles. */
    static TextView avatar(Context c, String letter, int color, int sizeDp) {
        TextView t = new TextView(c);
        t.setText(letter == null || letter.isEmpty() ? "?" : letter.substring(0, 1).toUpperCase());
        t.setTextColor(Color.WHITE);
        t.setTextSize(sizeDp >= 36 ? 16 : 13);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setGravity(Gravity.CENTER);
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.OVAL);
        g.setColor(color);
        t.setBackground(g);
        t.setLayoutParams(new LinearLayout.LayoutParams(dp(c, sizeDp), dp(c, sizeDp)));
        return t;
    }

    static int colorFor(String s) {
        int[] palette = {0xFF1A73E8, 0xFF188038, 0xFFE37400, 0xFFD93025, 0xFF9334E6, 0xFF129EAF, 0xFFC5221F, 0xFF5F6368, 0xFFB06000, 0xFF0B8043};
        int h = s == null ? 0 : s.toLowerCase().hashCode();
        return palette[Math.abs(h % palette.length)];
    }

    static String hostOf(String url) {
        try {
            String h = android.net.Uri.parse(url).getHost();
            if (h == null) return url == null ? "" : url;
            return h.startsWith("www.") ? h.substring(4) : h;
        } catch (Exception e) {
            return url == null ? "" : url;
        }
    }

    static EditText field(Context c, String hint, boolean password) {
        EditText e = new EditText(c);
        e.setHint(hint);
        e.setSingleLine(true);
        e.setTextSize(15);
        e.setTextColor(TEXT);
        e.setHintTextColor(TEXT3);
        e.setPadding(dp(c, 14), dp(c, 10), dp(c, 14), dp(c, 10));
        e.setBackground(box(c, SURFACE, 10, BORDER));
        if (password) e.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD);
        return e;
    }

    static TextView button(Context c, String label, boolean primary) {
        TextView b = text(c, label, 14, primary ? Color.WHITE : ACCENT, true);
        b.setGravity(Gravity.CENTER);
        b.setPadding(dp(c, 18), dp(c, 10), dp(c, 18), dp(c, 10));
        b.setBackground(ripple(c, primary ? ACCENT : Color.WHITE, 20, primary ? 0 : BORDER));
        b.setClickable(true);
        return b;
    }

    /** White sheet that slides up from the bottom. */
    static Dialog sheet(Activity a, View content) {
        final Dialog d = new Dialog(a);
        d.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout wrap = new LinearLayout(a);
        wrap.setOrientation(LinearLayout.VERTICAL);
        GradientDrawable g = new GradientDrawable();
        g.setColor(BG);
        float r = dp(a, 20);
        g.setCornerRadii(new float[]{r, r, r, r, 0, 0, 0, 0});
        wrap.setBackground(g);
        View handle = new View(a);
        handle.setBackground(box(a, BORDER, 3, 0));
        LinearLayout.LayoutParams hp = new LinearLayout.LayoutParams(dp(a, 36), dp(a, 4));
        hp.gravity = Gravity.CENTER_HORIZONTAL;
        hp.topMargin = dp(a, 8);
        hp.bottomMargin = dp(a, 4);
        wrap.addView(handle, hp);
        ScrollView sv = new ScrollView(a);
        sv.addView(content);
        wrap.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        d.setContentView(wrap);
        Window w = d.getWindow();
        if (w != null) {
            w.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            w.setGravity(Gravity.BOTTOM);
            w.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            w.setDimAmount(0.35f);
            w.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            if ((a.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_SECURE) != 0)
                w.addFlags(WindowManager.LayoutParams.FLAG_SECURE);                  // private tabs: no screenshots of menus either
            w.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        }
        return d;
    }

    /** Standard row: icon + title (+ optional subtitle). */
    static LinearLayout row(Context c, String iconName, String title, String sub, int tint) {
        LinearLayout r = new LinearLayout(c);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(dp(c, 18), dp(c, 12), dp(c, 18), dp(c, 12));
        r.setBackground(ripple(c, Color.TRANSPARENT, 0, 0));
        r.setClickable(true);
        if (iconName != null) {
            ImageView i = new ImageView(c);
            i.setImageDrawable(Ico.of(iconName, tint));
            r.addView(i, new LinearLayout.LayoutParams(dp(c, 22), dp(c, 22)));
            r.addView(space(c, 16, 1));
        }
        LinearLayout col = new LinearLayout(c);
        col.setOrientation(LinearLayout.VERTICAL);
        col.addView(oneLine(c, title, 15, TEXT, false));
        if (sub != null && !sub.isEmpty()) col.addView(oneLine(c, sub, 12, TEXT2, false));
        r.addView(col, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        return r;
    }

    static FrameLayout.LayoutParams match() {
        return new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
    }
}
