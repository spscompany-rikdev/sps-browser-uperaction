package com.spscompany.spsbrowser;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.security.MessageDigest;
import java.util.Locale;

/** Pure helpers for the in-app update check (GitHub release of this project). */
final class Updater {
    static final class Info {
        String version, notes, apkName, apkUrl, sumsUrl;
        long size;
    }

    private Updater() { }

    /** "v38.5.0" / "38.5.0" -> {38,5,0}; anything else -> null. */
    static int[] parse(String v) {
        if (v == null) return null;
        v = v.trim();
        if (v.startsWith("v") || v.startsWith("V")) v = v.substring(1);
        String[] p = v.split("\\.");
        if (p.length < 1 || p.length > 4) return null;
        int[] out = new int[4];
        try {
            for (int i = 0; i < p.length; i++) out[i] = Integer.parseInt(p[i].replaceAll("[^0-9].*$", ""));
        } catch (Exception e) { return null; }
        return out;
    }

    static boolean isNewer(String candidate, String current) {
        int[] a = parse(candidate), b = parse(current);
        if (a == null || b == null) return false;
        for (int i = 0; i < 4; i++) if (a[i] != b[i]) return a[i] > b[i];
        return false;
    }

    /** Reads GitHub's "latest release" JSON. Returns null when there is no usable .apk. Draft and pre-releases are ignored. */
    static Info fromRelease(String json) {
        try {
            JSONObject r = new JSONObject(json);
            if (r.optBoolean("draft") || r.optBoolean("prerelease")) return null;
            Info i = new Info();
            i.version = r.optString("tag_name", "").replaceFirst("^[vV]", "");
            i.notes = r.optString("body", "");
            JSONArray assets = r.optJSONArray("assets");
            if (assets == null) return null;
            for (int k = 0; k < assets.length(); k++) {
                JSONObject a = assets.getJSONObject(k);
                String name = a.optString("name", ""), url = a.optString("browser_download_url", "");
                if (!url.startsWith("https://")) continue;
                if (name.toLowerCase(Locale.ROOT).endsWith(".apk") && i.apkUrl == null) { i.apkName = name; i.apkUrl = url; i.size = a.optLong("size"); }
                if (name.equals("SHA256SUMS.txt")) i.sumsUrl = url;
            }
            return i.apkUrl == null || parse(i.version) == null ? null : i;
        } catch (Exception e) {
            return null;
        }
    }

    /** Finds the 64-hex checksum of fileName in the text of a SHA256SUMS file ("<hash>  <name>"). */
    static String hashFor(String sums, String fileName) {
        if (sums == null) return null;
        for (String line : sums.split("\\r?\\n")) {
            String t = line.trim();
            int sp = t.indexOf(' ');
            if (sp != 64) continue;
            String name = t.substring(sp).trim();
            if (name.startsWith("*")) name = name.substring(1);
            if (name.equals(fileName)) return t.substring(0, 64).toLowerCase(Locale.ROOT);
        }
        return null;
    }

    static String sha256(InputStream in) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] buf = new byte[65536];
        int n;
        while ((n = in.read(buf)) > 0) md.update(buf, 0, n);
        StringBuilder sb = new StringBuilder();
        for (byte b : md.digest()) sb.append(String.format("%02x", b));
        return sb.toString();
    }
}
