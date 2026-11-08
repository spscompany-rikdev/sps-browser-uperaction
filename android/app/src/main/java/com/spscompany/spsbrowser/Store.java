package com.spscompany.spsbrowser;

import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Everything the user saves (bookmarks, history, downloads list, saved passwords, autofill data) - encrypted on the phone with
 * Crypto. Old unencrypted data from earlier versions is encrypted automatically the first time it is read.
 * Passwords are NEVER written unencrypted: if the Keystore is unavailable, saving a password is refused.
 */
final class Store {
    private final SharedPreferences sp;
    private final Crypto crypto;
    private final boolean secure;
    private final Map<String, JSONArray> cache = new HashMap<>();
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    Store(SharedPreferences sp, String profileId) {
        this.sp = sp;
        this.crypto = new Crypto(profileId);
        this.secure = crypto.works();
    }

    boolean isSecure() { return secure; }

    Crypto crypto() { return crypto; }

    // ───────────── generic encrypted JSON arrays ─────────────
    private synchronized JSONArray arr(String key, boolean needsSecurity) {
        JSONArray a = cache.get(key);
        if (a != null) return a;
        a = new JSONArray();
        try {
            String enc = sp.getString("e_" + key, null);
            if (enc != null) {
                if (secure) a = new JSONArray(crypto.dec(key, enc));
            } else if (sp.contains(key)) {                         // older plain data: move it into the encrypted store
                a = new JSONArray(sp.getString(key, "[]"));
                cache.put(key, a);
                if (secure || !needsSecurity) { persist(key); sp.edit().remove(key).apply(); }
            }
        } catch (Exception ignored) { }
        cache.put(key, a);
        return a;
    }

    private void persist(final String key) {
        final String json;
        synchronized (this) { json = cache.containsKey(key) ? cache.get(key).toString() : "[]"; }
        io.execute(() -> {
            try {
                if (secure) sp.edit().putString("e_" + key, crypto.enc(key, json)).apply();
                else if (!key.equals("vault") && !key.equals("autofill")) sp.edit().putString(key, json).apply();
            } catch (Exception ignored) { }
        });
    }

    private synchronized void put(String key, JSONArray a) {
        cache.put(key, a);
        persist(key);
    }

    static String newId() { return UUID.randomUUID().toString().substring(0, 12); }

    private static List<JSONObject> asList(JSONArray a) {
        ArrayList<JSONObject> l = new ArrayList<>();
        for (int i = 0; i < a.length(); i++) { JSONObject o = a.optJSONObject(i); if (o != null) l.add(o); }
        return l;
    }

    private synchronized void write(String key, List<JSONObject> l) {
        JSONArray a = new JSONArray();
        for (JSONObject o : l) a.put(o);
        put(key, a);
    }

    // ───────────── bookmarks ─────────────
    synchronized List<JSONObject> bookmarks() { return asList(arr("bookmarks", false)); }

    synchronized boolean isBookmarked(String url) {
        for (JSONObject o : bookmarks()) if (url != null && url.equals(o.optString("u"))) return true;
        return false;
    }

    synchronized void addBookmark(String title, String url) {
        if (isBookmarked(url)) return;
        try {
            JSONObject o = new JSONObject();
            o.put("id", newId()); o.put("t", title == null || title.isEmpty() ? url : title); o.put("u", url); o.put("ts", System.currentTimeMillis());
            arr("bookmarks", false).put(o);
            persist("bookmarks");
        } catch (Exception ignored) { }
    }

    synchronized void removeBookmarkUrl(String url) {
        List<JSONObject> l = bookmarks(), out = new ArrayList<>();
        for (JSONObject o : l) if (!o.optString("u").equals(url)) out.add(o);
        write("bookmarks", out);
    }

    synchronized void removeBookmarks(java.util.Set<String> ids) {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject o : bookmarks()) if (!ids.contains(o.optString("id"))) out.add(o);
        write("bookmarks", out);
    }

    synchronized void renameBookmark(String id, String title, String url) {
        for (JSONObject o : bookmarks()) if (o.optString("id").equals(id)) {
            try { o.put("t", title); o.put("u", url); } catch (Exception ignored) { }
        }
        persist("bookmarks");
    }

    // ───────────── history ─────────────
    synchronized List<JSONObject> history() { return asList(arr("history", false)); }

    synchronized void addHistory(String title, String url) {
        try {
            JSONArray h = arr("history", false);
            if (h.length() > 0) {
                JSONObject last = h.optJSONObject(h.length() - 1);
                if (last != null && url.equals(last.optString("u"))) return;
            }
            JSONObject o = new JSONObject();
            o.put("id", newId()); o.put("t", title == null || title.isEmpty() ? url : title); o.put("u", url); o.put("ts", System.currentTimeMillis());
            h.put(o);
            if (h.length() > 3000) {
                JSONArray t = new JSONArray();
                for (int i = h.length() - 3000; i < h.length(); i++) t.put(h.get(i));
                cache.put("history", t);
            }
            persist("history");
        } catch (Exception ignored) { }
    }

    synchronized void removeHistory(java.util.Set<String> ids) {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject o : history()) if (!ids.contains(o.optString("id"))) out.add(o);
        write("history", out);
    }

    synchronized void clearHistory() { put("history", new JSONArray()); }

    // ───────────── downloads list (the files themselves are handled by Android's DownloadManager) ─────────────
    synchronized List<JSONObject> downloads() { return asList(arr("downloads", false)); }

    synchronized void addDownload(long id, String name, String url) {
        try {
            JSONObject o = new JSONObject();
            o.put("id", String.valueOf(id)); o.put("n", name); o.put("u", url == null ? "" : url); o.put("ts", System.currentTimeMillis());
            JSONArray a = arr("downloads", false);
            a.put(o);
            if (a.length() > 300) {
                JSONArray t = new JSONArray();
                for (int i = a.length() - 300; i < a.length(); i++) t.put(a.get(i));
                cache.put("downloads", t);
            }
            persist("downloads");
        } catch (Exception ignored) { }
    }

    synchronized void removeDownloads(java.util.Set<String> ids) {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject o : downloads()) if (!ids.contains(o.optString("id"))) out.add(o);
        write("downloads", out);
    }

    // ───────────── password vault ─────────────
    synchronized List<JSONObject> vault() { return secure ? asList(arr("vault", true)) : new ArrayList<JSONObject>(); }

    /** Adds or replaces (same id). Returns false when the device cannot encrypt. */
    synchronized boolean saveLogin(String id, String host, String user, String pass, String notes) {
        if (!secure) return false;
        try {
            List<JSONObject> l = vault();
            JSONObject target = null;
            if (id != null) for (JSONObject o : l) if (o.optString("id").equals(id)) target = o;
            if (target == null) for (JSONObject o : l) if (o.optString("h").equals(host) && o.optString("u").equals(user)) target = o;
            boolean isNew = target == null;
            if (isNew) { target = new JSONObject(); target.put("id", newId()); target.put("ts", System.currentTimeMillis()); l.add(target); }
            target.put("h", host); target.put("u", user); target.put("p", pass); target.put("n", notes == null ? "" : notes);
            target.put("mt", System.currentTimeMillis());
            write("vault", l);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    synchronized void removeLogins(java.util.Set<String> ids) {
        List<JSONObject> out = new ArrayList<>();
        for (JSONObject o : vault()) if (!ids.contains(o.optString("id"))) out.add(o);
        write("vault", out);
    }

    /** Logins that belong to this site (same host, or a parent domain such as accounts.example.com -> example.com). */
    synchronized List<JSONObject> loginsFor(String host) {
        List<JSONObject> r = new ArrayList<>();
        if (host == null) return r;
        for (JSONObject o : vault()) {
            String h = o.optString("h");
            if (h.equals(host) || host.endsWith("." + h) || h.endsWith("." + host)) r.add(o);
        }
        return r;
    }

    synchronized boolean hasLogin(String host, String user) {
        for (JSONObject o : vault()) if (o.optString("h").equals(host) && o.optString("u").equals(user)) return true;
        return false;
    }

    synchronized boolean samePassword(String host, String user, String pass) {
        for (JSONObject o : vault()) if (o.optString("h").equals(host) && o.optString("u").equals(user) && o.optString("p").equals(pass)) return true;
        return false;
    }

    // ───────────── autofill profile (name, address ...) ─────────────
    synchronized JSONObject autofill() {
        JSONArray a = arr("autofill", true);
        JSONObject o = a.length() > 0 ? a.optJSONObject(0) : null;
        return o == null ? new JSONObject() : o;
    }

    synchronized boolean saveAutofill(JSONObject o) {
        if (!secure) return false;
        JSONArray a = new JSONArray();
        a.put(o);
        put("autofill", a);
        return true;
    }

    // ───────────── wipe ─────────────
    synchronized void wipeAll() {
        cache.clear();
        sp.edit().remove("e_bookmarks").remove("e_history").remove("e_downloads").remove("e_vault").remove("e_autofill")
                .remove("bookmarks").remove("history").remove("downloads").apply();
        crypto.deleteKey();
    }
}
