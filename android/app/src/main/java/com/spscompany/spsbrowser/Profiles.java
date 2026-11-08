package com.spscompany.spsbrowser;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import android.webkit.WebView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Browser profiles. Each profile has its own settings, bookmarks, history, passwords and (Android 9+) its own cookies / logins,
 * so for example "Work" and "Personal" never mix. The first profile ("Default") keeps using the old storage so nothing is lost.
 */
final class Profiles {
    static final class Profile {
        String id, name;
        int color;
    }

    private final SharedPreferences meta;
    private final Context ctx;

    Profiles(Context c) {
        ctx = c.getApplicationContext();
        meta = ctx.getSharedPreferences("sps_profiles", Context.MODE_PRIVATE);
        if (list().isEmpty()) {
            Profile d = new Profile();
            d.id = "default"; d.name = "Default"; d.color = 0xFF1A73E8;
            List<Profile> l = new ArrayList<>();
            l.add(d);
            save(l, "default");
        }
    }

    List<Profile> list() {
        List<Profile> l = new ArrayList<>();
        try {
            JSONArray a = new JSONArray(meta.getString("list", "[]"));
            for (int i = 0; i < a.length(); i++) {
                JSONObject o = a.getJSONObject(i);
                Profile p = new Profile();
                p.id = o.getString("id"); p.name = o.getString("name"); p.color = o.optInt("color", 0xFF1A73E8);
                l.add(p);
            }
        } catch (Exception ignored) { }
        return l;
    }

    private void save(List<Profile> l, String active) {
        try {
            JSONArray a = new JSONArray();
            for (Profile p : l) {
                JSONObject o = new JSONObject();
                o.put("id", p.id); o.put("name", p.name); o.put("color", p.color);
                a.put(o);
            }
            meta.edit().putString("list", a.toString()).putString("active", active).apply();
        } catch (Exception ignored) { }
    }

    String activeId() {
        String a = meta.getString("active", "default");
        for (Profile p : list()) if (p.id.equals(a)) return a;
        return "default";
    }

    Profile active() {
        String a = activeId();
        for (Profile p : list()) if (p.id.equals(a)) return p;
        return list().get(0);
    }

    Profile add(String name, int color) {
        List<Profile> l = list();
        Profile p = new Profile();
        p.id = Store.newId(); p.name = name; p.color = color;
        l.add(p);
        save(l, activeId());
        return p;
    }

    void rename(String id, String name, int color) {
        List<Profile> l = list();
        for (Profile p : l) if (p.id.equals(id)) { p.name = name; p.color = color; }
        save(l, activeId());
    }

    void setActive(String id) {
        save(list(), id);
    }

    String prefsName(String id) {
        return id.equals("default") ? "sps" : "sps_p_" + id;
    }

    /** Deletes a profile and everything saved in it (not the Default profile). */
    void delete(String id) {
        if (id.equals("default")) return;
        List<Profile> l = list();
        List<Profile> keep = new ArrayList<>();
        for (Profile p : l) if (!p.id.equals(id)) keep.add(p);
        String active = activeId().equals(id) ? "default" : activeId();
        save(keep, active);
        SharedPreferences sp = ctx.getSharedPreferences(prefsName(id), Context.MODE_PRIVATE);
        new Store(sp, id).wipeAll();
        sp.edit().clear().apply();
        try { new File(ctx.getFilesDir().getParentFile(), "shared_prefs/" + prefsName(id) + ".xml").delete(); } catch (Exception ignored) { }
        deleteDir(ctx.getDir("webview_" + id, Context.MODE_PRIVATE));
    }

    /** Must run before the first WebView exists in the process. Android 9+ keeps cookies and site data per profile. */
    void applyWebViewData() {
        String id = activeId();
        if (id.equals("default") || Build.VERSION.SDK_INT < 28) return;
        try {
            WebView.setDataDirectorySuffix(id);
        } catch (Throwable ignored) { }
    }

    static boolean separateCookies() { return Build.VERSION.SDK_INT >= 28; }

    private static void deleteDir(File f) {
        if (f == null || !f.exists()) return;
        File[] kids = f.listFiles();
        if (kids != null) for (File k : kids) deleteDir(k);
        f.delete();
    }
}
