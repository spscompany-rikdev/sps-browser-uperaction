package com.spscompany.spsbrowser;

import android.app.AlertDialog;
import android.app.Dialog;
import android.content.Context;
import android.graphics.Color;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Password manager screens: list with health check, editor, generator and the autofill profile. */
final class Vault {
    private Vault() { }

    // ───────────── list ─────────────
    static void openList(final Host h) {
        h.unlock(() -> {
            ListPage p = new ListPage(h, "Passwords", () -> loginItems(h), it -> openEditor(h, (JSONObject) it.tag))
                    .empty("No saved passwords yet.\nThey are saved when you sign in to a site, or add one with the menu.", "key")
                    .bulk("Delete", "trash", true, sel -> {
                        Set<String> ids = new HashSet<>();
                        for (ListPage.Item it : sel) ids.add(it.id);
                        h.store().removeLogins(ids);
                        h.toast(ids.size() + " deleted");
                    });
            p.menu("Add password", false, s -> openEditor(h, null));
            p.menu("Password generator", false, s -> generator(h, null));
            p.menu("Autofill info (name, address ...)", false, s -> openAutofill(h));
            h.push(p);
        });
    }

    private static List<ListPage.Item> loginItems(Host h) {
        List<JSONObject> all = h.store().vault();
        Map<String, Integer> count = new HashMap<>();
        for (JSONObject o : all) { String p = o.optString("p"); count.put(p, count.containsKey(p) ? count.get(p) + 1 : 1); }
        List<ListPage.Item> out = new ArrayList<>();
        java.util.Collections.sort(all, (a, b) -> a.optString("h").compareToIgnoreCase(b.optString("h")));
        for (JSONObject o : all) {
            ListPage.Item it = new ListPage.Item();
            it.id = o.optString("id");
            it.title = o.optString("h");
            it.sub = o.optString("u");
            it.tag = o;
            String p = o.optString("p");
            if (count.get(p) > 1) { it.trailing = "Reused"; it.warn = true; }
            else if (PasswordGen.level(p) == 0) { it.trailing = "Weak"; it.warn = true; }
            String first = it.title.isEmpty() ? "?" : it.title.substring(0, 1).toUpperCase();
            it.section = first;
            out.add(it);
        }
        return out;
    }

    // ───────────── editor ─────────────
    static void openEditor(final Host h, final JSONObject existing) {
        final Context c = h.act();
        final LinearLayout page = new LinearLayout(c);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setBackgroundColor(UI.BG);
        page.setClickable(true);
        class EditorPage extends LinearLayout implements Page {
            EditorPage() { super(c); }
            @Override public boolean onBack() { return false; }
        }
        final EditorPage root = new EditorPage();
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(UI.BG);
        root.setClickable(true);
        root.addView(topBar(h, existing == null ? "Add password" : "Edit password"));
        root.addView(UI.divider(c));
        LinearLayout form = new LinearLayout(c);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(UI.dp(c, 18), UI.dp(c, 14), UI.dp(c, 18), UI.dp(c, 24));
        final EditText site = UI.field(c, "Website (example.com)", false);
        final EditText user = UI.field(c, "Username or email", false);
        final EditText pass = UI.field(c, "Password", true);
        final EditText notes = UI.field(c, "Notes (optional)", false);
        notes.setSingleLine(false);
        notes.setMinLines(2);
        final boolean[] revealed = {false};
        if (existing != null) {
            site.setText(existing.optString("h"));
            user.setText(existing.optString("u"));
            pass.setText(existing.optString("p"));
            notes.setText(existing.optString("n"));
        }
        form.addView(label(c, "Website")); form.addView(site);
        form.addView(label(c, "Username")); form.addView(user);
        LinearLayout copyRow = new LinearLayout(c);
        form.addView(label(c, "Password"));
        final LinearLayout passRow = new LinearLayout(c);
        passRow.setGravity(Gravity.CENTER_VERTICAL);
        passRow.addView(pass, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        final ImageView eye = UI.icon(c, "eye", UI.TEXT2, 44, 11);
        passRow.addView(eye);
        form.addView(passRow);
        final ProgressBar meter = new ProgressBar(c, null, android.R.attr.progressBarStyleHorizontal);
        meter.setMax(100);
        LinearLayout.LayoutParams mp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, UI.dp(c, 5));
        mp.topMargin = UI.dp(c, 8);
        form.addView(meter, mp);
        final TextView strength = UI.text(c, "", 12, UI.TEXT2, false);
        form.addView(strength);
        TextView gen = UI.button(c, "Generate strong password", false);
        LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        gp.topMargin = UI.dp(c, 10);
        form.addView(gen, gp);
        form.addView(label(c, "Notes")); form.addView(notes);

        final Runnable updateMeter = () -> {
            String p = pass.getText().toString();
            int lv = PasswordGen.level(p);
            double b = Math.min(100, PasswordGen.bits(p));
            meter.setProgress((int) b);
            meter.setProgressTintList(android.content.res.ColorStateList.valueOf(PasswordGen.levelColor(lv)));
            strength.setText(p.isEmpty() ? "" : PasswordGen.levelName(lv) + " password");
            strength.setTextColor(PasswordGen.levelColor(lv));
        };
        pass.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int a, int b, int d) { }
            @Override public void onTextChanged(CharSequence s, int a, int b, int d) { updateMeter.run(); }
            @Override public void afterTextChanged(Editable s) { }
        });
        updateMeter.run();
        eye.setOnClickListener(v -> {
            revealed[0] = !revealed[0];
            int sel = pass.getSelectionStart();
            pass.setInputType(android.text.InputType.TYPE_CLASS_TEXT | (revealed[0]
                    ? android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD : android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD));
            UI.setIcon(eye, revealed[0] ? "eyeoff" : "eye", UI.TEXT2);
            if (sel >= 0) pass.setSelection(Math.min(sel, pass.getText().length()));
        });
        gen.setOnClickListener(v -> generator(h, pw -> pass.setText(pw)));

        LinearLayout buttons = new LinearLayout(c);
        buttons.setGravity(Gravity.END);
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        bp.topMargin = UI.dp(c, 22);
        if (existing != null) {
            TextView cu = UI.button(c, "Copy user", false);
            cu.setOnClickListener(v -> h.copySecret(user.getText().toString()));
            TextView cp = UI.button(c, "Copy password", false);
            cp.setOnClickListener(v -> h.copySecret(pass.getText().toString()));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.rightMargin = UI.dp(c, 8);
            buttons.addView(cu, lp);
            buttons.addView(cp, lp);
        }
        TextView save = UI.button(c, "Save", true);
        save.setOnClickListener(v -> {
            String s = site.getText().toString().trim().toLowerCase().replace("https://", "").replace("http://", "");
            int slash = s.indexOf('/');
            if (slash > 0) s = s.substring(0, slash);
            if (s.startsWith("www.")) s = s.substring(4);
            String u = user.getText().toString().trim();
            String p = pass.getText().toString();
            if (s.isEmpty() || p.isEmpty()) { h.toast("Enter the website and the password"); return; }
            boolean ok = h.store().saveLogin(existing == null ? null : existing.optString("id"), s, u, p, notes.getText().toString());
            if (!ok) { h.toast("This phone cannot encrypt passwords, so nothing was saved"); return; }
            h.toast("Saved");
            h.pop();
            refreshTop(h);
        });
        buttons.addView(save);
        form.addView(buttons, bp);
        if (existing != null) {
            TextView del = UI.button(c, "Delete this password", false);
            del.setTextColor(UI.DANGER);
            del.setOnClickListener(v -> new AlertDialog.Builder(h.act()).setMessage("Delete the saved password for " + existing.optString("h") + "?")
                    .setPositiveButton("Delete", (d, w) -> {
                        Set<String> ids = new HashSet<>();
                        ids.add(existing.optString("id"));
                        h.store().removeLogins(ids);
                        h.pop();
                        refreshTop(h);
                    }).setNegativeButton("Cancel", null).show());
            LinearLayout.LayoutParams dp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            dp.topMargin = UI.dp(c, 18);
            form.addView(del, dp);
        }
        ScrollView sv = new ScrollView(c);
        sv.addView(form);
        root.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        h.push(root);
    }

    private static void refreshTop(Host h) {
        if (h instanceof MainActivity) ((MainActivity) h).refreshTopPage();
    }

    static View topBar(final Host h, String title) {
        Context c = h.act();
        LinearLayout bar = new LinearLayout(c);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        bar.setPadding(UI.dp(c, 4), 0, UI.dp(c, 12), 0);
        ImageView back = UI.icon(c, "back", UI.TEXT, 44, 11);
        back.setOnClickListener(v -> h.pop());
        bar.addView(back);
        TextView t = UI.text(c, title, 19, UI.TEXT, true);
        t.setPadding(UI.dp(c, 4), 0, 0, 0);
        bar.addView(t);
        bar.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, UI.dp(c, 56)));
        return bar;
    }

    private static TextView label(Context c, String s) {
        TextView t = UI.text(c, s, 12, UI.TEXT2, true);
        t.setPadding(0, UI.dp(c, 14), 0, UI.dp(c, 4));
        return t;
    }

    // ───────────── generator ─────────────
    interface Use { void use(String password); }

    static void generator(final Host h, final Use use) {
        final Context c = h.act();
        LinearLayout box = new LinearLayout(c);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(UI.dp(c, 20), UI.dp(c, 8), UI.dp(c, 20), UI.dp(c, 20));
        box.addView(UI.text(c, "Password generator", 18, UI.TEXT, true));
        final TextView out = UI.text(c, "", 20, UI.ACCENT, true);
        out.setTypeface(android.graphics.Typeface.MONOSPACE, android.graphics.Typeface.BOLD);
        out.setPadding(UI.dp(c, 14), UI.dp(c, 14), UI.dp(c, 14), UI.dp(c, 14));
        out.setBackground(UI.box(c, UI.SURFACE, 12, UI.BORDER));
        out.setTextIsSelectable(true);
        LinearLayout.LayoutParams op = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        op.topMargin = UI.dp(c, 12);
        box.addView(out, op);
        final TextView strength = UI.text(c, "", 12, UI.TEXT2, true);
        box.addView(strength);
        final TextView lenLabel = UI.text(c, "", 13, UI.TEXT, false);
        box.addView(lenLabel);
        final SeekBar sb = new SeekBar(c);
        sb.setMax(56);
        sb.setProgress(12);
        box.addView(sb);
        final CheckBox up = check(c, "Uppercase A-Z", true), lo = check(c, "Lowercase a-z", true), di = check(c, "Digits 0-9", true),
                sy = check(c, "Symbols !@#", true), am = check(c, "Avoid look-alike characters (0 O 1 l I)", true),
                words = check(c, "Easy to remember (words)", false);
        for (CheckBox cb : new CheckBox[]{up, lo, di, sy, am, words}) box.addView(cb);
        final Runnable regen = () -> {
            int len = sb.getProgress() + 8;
            String p;
            if (words.isChecked()) {
                int n = Math.max(3, Math.min(8, len / 5 + 1));
                lenLabel.setText("Words: " + n);
                p = PasswordGen.words(n, up.isChecked(), di.isChecked());
            } else {
                lenLabel.setText("Length: " + len);
                p = PasswordGen.random(len, up.isChecked(), lo.isChecked(), di.isChecked(), sy.isChecked(), am.isChecked());
            }
            out.setText(p);
            int lv = PasswordGen.level(p);
            strength.setText(PasswordGen.levelName(lv) + "  •  about " + (int) PasswordGen.bits(p) + " bits");
            strength.setTextColor(PasswordGen.levelColor(lv));
        };
        SeekBar.OnSeekBarChangeListener sl = new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar s, int p, boolean user) { regen.run(); }
            @Override public void onStartTrackingTouch(SeekBar s) { }
            @Override public void onStopTrackingTouch(SeekBar s) { }
        };
        sb.setOnSeekBarChangeListener(sl);
        for (CheckBox cb : new CheckBox[]{up, lo, di, sy, am, words}) cb.setOnCheckedChangeListener((b, v) -> regen.run());
        LinearLayout btns = new LinearLayout(c);
        btns.setGravity(Gravity.END);
        final Dialog[] d = new Dialog[1];
        TextView again = UI.button(c, "New", false);
        again.setOnClickListener(v -> regen.run());
        TextView copy = UI.button(c, "Copy", false);
        copy.setOnClickListener(v -> h.copySecret(out.getText().toString()));
        btns.addView(again);
        btns.addView(copy);
        if (use != null) {
            TextView useBtn = UI.button(c, "Use", true);
            useBtn.setOnClickListener(v -> { use.use(out.getText().toString()); d[0].dismiss(); });
            btns.addView(useBtn);
        }
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        bp.topMargin = UI.dp(c, 14);
        box.addView(btns, bp);
        regen.run();
        d[0] = UI.sheet(h.act(), box);
        d[0].show();
    }

    private static CheckBox check(Context c, String label, boolean on) {
        CheckBox cb = new CheckBox(c);
        cb.setText(label);
        cb.setTextColor(UI.TEXT);
        cb.setChecked(on);
        return cb;
    }

    // ───────────── autofill profile ─────────────
    static final String[][] FIELDS = {
            {"name", "Full name"}, {"email", "Email"}, {"phone", "Phone"}, {"org", "Company"}, {"addr", "Street address"},
            {"city", "City"}, {"state", "State / region"}, {"zip", "Postal code"}, {"country", "Country"}};

    static void openAutofill(final Host h) {
        final Context c = h.act();
        class P extends LinearLayout implements Page {
            P() { super(c); }
            @Override public boolean onBack() { return false; }
        }
        P root = new P();
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(UI.BG);
        root.setClickable(true);
        root.addView(topBar(h, "Autofill info"));
        root.addView(UI.divider(c));
        LinearLayout form = new LinearLayout(c);
        form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(UI.dp(c, 18), UI.dp(c, 10), UI.dp(c, 18), UI.dp(c, 24));
        form.addView(UI.text(c, "Saved only on this phone, encrypted. Use “Fill form” in the menu to put it into a web form.", 12, UI.TEXT2, false));
        final JSONObject cur = h.store().autofill();
        final List<EditText> fields = new ArrayList<>();
        for (String[] f : FIELDS) {
            form.addView(label(c, f[1]));
            EditText e = UI.field(c, f[1], false);
            e.setText(cur.optString(f[0]));
            fields.add(e);
            form.addView(e);
        }
        TextView save = UI.button(c, "Save", true);
        save.setOnClickListener(v -> {
            JSONObject o = new JSONObject();
            try { for (int i = 0; i < FIELDS.length; i++) o.put(FIELDS[i][0], fields.get(i).getText().toString().trim()); } catch (Exception ignored) { }
            if (h.store().saveAutofill(o)) { h.toast("Saved"); h.pop(); } else h.toast("This phone cannot encrypt, so nothing was saved");
        });
        LinearLayout.LayoutParams sp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        sp.topMargin = UI.dp(c, 20);
        sp.gravity = Gravity.END;
        form.addView(save, sp);
        ScrollView sv = new ScrollView(c);
        sv.addView(form);
        root.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
        h.push(root);
    }
}
