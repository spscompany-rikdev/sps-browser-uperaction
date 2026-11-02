package com.spscompany.spsbrowser;

import java.util.Locale;
import java.util.Set;

/** Privacy-shield logic without Android classes, so it can be unit-tested on any computer. */
final class Shield {
    private Shield() { }

    private static final String[] PARAMS = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id", "fbclid", "gclid", "dclid", "gbraid", "wbraid",
            "msclkid", "yclid", "mc_eid", "igshid", "_hsenc", "_hsmi", "mkt_tok", "vero_id", "twclid", "ttclid", "li_fat_id",
            "oly_anon_id", "oly_enc_id", "ref_src", "ref_url"};

    private static boolean isTracking(String name) {
        String n = name.toLowerCase(Locale.ROOT);
        if (n.startsWith("utm_")) return true;
        for (String p : PARAMS) if (n.equals(p)) return true;
        return false;
    }

    /** Removes tracking parts (utm_*, fbclid, gclid ...) from an address. Returns the same text when there is nothing to remove. */
    static String stripTracking(String url) {
        if (url == null) return null;
        int q = url.indexOf('?');
        if (q < 0) return url;
        int hash = url.indexOf('#', q);
        String query = hash < 0 ? url.substring(q + 1) : url.substring(q + 1, hash);
        String frag = hash < 0 ? "" : url.substring(hash);
        StringBuilder keep = new StringBuilder();
        boolean removed = false;
        for (String part : query.split("&")) {
            if (part.isEmpty()) continue;
            int eq = part.indexOf('=');
            String name = eq < 0 ? part : part.substring(0, eq);
            if (isTracking(name)) { removed = true; continue; }
            if (keep.length() > 0) keep.append('&');
            keep.append(part);
        }
        if (!removed) return url;
        return url.substring(0, q) + (keep.length() > 0 ? "?" + keep : "") + frag;
    }

    /** True when the host, or any parent domain of it, is in the set (ads.example.com matches example.com). */
    static boolean hostBlocked(String host, Set<String> blocked) {
        if (host == null) return false;
        String h = host.toLowerCase(Locale.ROOT);
        while (h.indexOf('.') > 0) {
            if (blocked.contains(h)) return true;
            h = h.substring(h.indexOf('.') + 1);
        }
        return false;
    }

    /** Site name of a host: last two labels (three for endings such as co.uk). Good enough to tell first-party from third-party. */
    static String site(String host) {
        String[] l = host.toLowerCase(Locale.ROOT).split("\\.");
        int n = l.length;
        if (n <= 2) return host.toLowerCase(Locale.ROOT);
        boolean two = l[n - 1].length() == 2 && (l[n - 2].equals("co") || l[n - 2].equals("com") || l[n - 2].equals("org")
                || l[n - 2].equals("net") || l[n - 2].equals("gov") || l[n - 2].equals("edu") || l[n - 2].equals("ac"));
        int k = two ? 3 : 2;
        return String.join(".", java.util.Arrays.copyOfRange(l, n - k, n));
    }

    /** A request is third-party when it goes to a different site than the page. */
    static boolean isThirdParty(String pageHost, String reqHost) {
        if (pageHost == null || reqHost == null) return true;
        return !site(pageHost).equals(site(reqHost));
    }
}
