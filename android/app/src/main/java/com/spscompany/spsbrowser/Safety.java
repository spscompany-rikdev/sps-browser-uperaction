package com.spscompany.spsbrowser;

import org.json.JSONObject;

import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Safety Check (logic only, no Android classes, so it runs on a normal JVM in the tests).
 * Leaked passwords: only the FIRST 5 characters of the password's SHA-1 are sent (k-anonymity); the match is made on the phone.
 */
final class Safety {
    private Safety() { }

    static final String OK = "ok", WARN = "warn", BAD = "bad", INFO = "info";
    static final String HIBP = "https://api.pwnedpasswords.com/range/";

    static final class Result {
        final String level, title, detail;
        Result(String level, String title, String detail) { this.level = level; this.title = title; this.detail = detail; }
    }

    interface Fetch { String get(String url) throws Exception; }

    static String[] sha1Parts(String pw) throws Exception {
        byte[] d = MessageDigest.getInstance("SHA-1").digest(pw.getBytes("UTF-8"));
        StringBuilder sb = new StringBuilder();
        for (byte b : d) sb.append(String.format(Locale.US, "%02X", b));
        return new String[]{sb.substring(0, 5), sb.substring(5)};
    }

    static int pwnedCount(String pw, Fetch f, Map<String, String> cache) throws Exception {
        String[] p = sha1Parts(pw);
        String body = cache.get(p[0]);
        if (body == null) { body = f.get(HIBP + p[0]); cache.put(p[0], body); }
        for (String line : body.split("\\r?\\n")) {
            int i = line.indexOf(':');
            if (i > 0 && line.substring(0, i).trim().equalsIgnoreCase(p[1])) {
                try { return Integer.parseInt(line.substring(i + 1).trim()); } catch (NumberFormatException e) { return 1; }
            }
        }
        return 0;
    }

    private static final Set<String> COMMON = new HashSet<>(java.util.Arrays.asList(
            "password", "123456", "12345678", "123456789", "qwerty", "abc123", "111111", "letmein", "iloveyou", "admin", "welcome",
            "password1", "123123", "000000", "qwerty123", "1q2w3e4r", "dragon", "monkey", "football", "sunshine"));

    static String weakReason(String pw) {
        if (pw == null || pw.isEmpty()) return "empty";
        if (COMMON.contains(pw.toLowerCase(Locale.US))) return "one of the most common passwords";
        if (pw.length() < 8) return "shorter than 8 characters";
        Set<Character> u = new HashSet<>();
        for (char ch : pw.toCharArray()) u.add(ch);
        if (u.size() <= 3) return "almost only repeated characters";
        if (pw.matches("\\d+") || pw.matches("\\p{L}+")) return "only digits or only letters";
        return null;
    }

    /** logins: JSON objects with h (site), u (user), p (password), as saved by the vault. */
    static List<Result> checkPasswords(List<JSONObject> logins, Fetch f) {
        List<Result> res = new ArrayList<>();
        Map<String, List<JSONObject>> byPw = new HashMap<>();
        for (JSONObject o : logins) {
            String p = o.optString("p");
            if (p.isEmpty()) continue;
            List<JSONObject> l = byPw.get(p);
            if (l == null) { l = new ArrayList<>(); byPw.put(p, l); }
            l.add(o);
        }
        if (byPw.isEmpty()) { res.add(new Result(INFO, "Saved passwords", "No saved passwords to check.")); return res; }
        Map<String, String> cache = new HashMap<>();
        boolean net = true, problem = false;
        int total = 0;
        for (Map.Entry<String, List<JSONObject>> e : byPw.entrySet()) {
            String pw = e.getKey();
            StringBuilder names = new StringBuilder();
            Set<String> seen = new HashSet<>();
            for (JSONObject o : e.getValue()) { total++; String h = o.optString("h", "?"); if (seen.add(h) && names.length() < 90) names.append(names.length() > 0 ? ", " : "").append(h); }
            if (e.getValue().size() > 1) { problem = true; res.add(new Result(WARN, "Reused password", "The same password is used for: " + names)); }
            String wr = weakReason(pw);
            if (wr != null) { problem = true; res.add(new Result(WARN, "Weak password", names + " - " + wr)); }
            if (net) {
                try {
                    int n = pwnedCount(pw, f, cache);
                    if (n > 0) { problem = true; res.add(new Result(BAD, "Password found in a data leak", names + " - seen " + n + " times in known leaks. Change it.")); }
                } catch (Exception ex) {
                    net = false;
                    res.add(new Result(INFO, "Leak check skipped", "No connection to the check service. Nothing was sent."));
                }
            }
        }
        if (!problem && net) res.add(new Result(OK, "Saved passwords", total + " password(s) checked: none leaked, reused or weak."));
        return res;
    }

    private static final Object[][] RULES = {
            {"\\beval\\s*\\(|new\\s+Function\\s*\\(", 2, "runs code built at run time (eval)"},
            {"createElement\\(\\s*['\"]script['\"]\\s*\\)", 2, "loads more code from the internet"},
            {"document\\.cookie", 2, "reads cookies"},
            {"type\\s*=\\s*['\"]?password|input\\[type=password\\]|querySelector\\([^)]*password", 3, "looks at password fields"},
            {"addEventListener\\(\\s*['\"]key(down|up|press)['\"]", 1, "listens to the keyboard"},
            {"XMLHttpRequest|fetch\\s*\\(|sendBeacon|new\\s+WebSocket", 1, "sends data to servers"},
            {"atob\\s*\\(|String\\.fromCharCode", 2, "hides its code (obfuscation)"},
            {"localStorage|sessionStorage|indexedDB", 1, "reads saved site data"},
    };

    /** Heuristic look at a user script. Returns null when nothing is suspicious, else a sentence. */
    static Result analyzeScript(String name, String match, String code) {
        int score = 0;
        List<String> why = new ArrayList<>();
        for (Object[] r : RULES) {
            if (Pattern.compile((String) r[0]).matcher(code == null ? "" : code).find()) { score += (Integer) r[1]; why.add((String) r[2]); }
        }
        String m = match == null ? "*" : match.trim();
        if (m.isEmpty() || m.equals("*") || m.equals("<all_urls>") || m.equals("*://*/*") || m.contains("all_urls")) { score += 1; why.add("runs on every website"); }
        boolean sends = why.contains("sends data to servers");
        boolean steals = why.contains("reads cookies") || why.contains("looks at password fields");
        if (sends && steals) { score += 3; why.add("can read private data AND send it out"); }
        if (score < 3) return null;
        StringBuilder sb = new StringBuilder("Could be risky - it ");
        for (int i = 0; i < Math.min(4, why.size()); i++) sb.append(i > 0 ? "; " : "").append(why.get(i));
        sb.append(". Remove it if you do not know it.");
        return new Result(score >= 7 ? BAD : WARN, "Script: " + name, sb.toString());
    }

    static Result checkVersion(String current, String latest) {
        if (latest == null) return new Result(INFO, "App version", "Could not check for updates.");
        if (Updater.isNewer(latest, current)) return new Result(WARN, "App version", "Version " + latest + " is available (you have " + current + "). Update for the latest security fixes.");
        return new Result(OK, "App version", "You have the newest version (" + current + ").");
    }

    static Result setting(boolean on, String title, String hint) {
        return on ? new Result(OK, title, "On.") : new Result(WARN, title, "Off. " + hint);
    }
}
