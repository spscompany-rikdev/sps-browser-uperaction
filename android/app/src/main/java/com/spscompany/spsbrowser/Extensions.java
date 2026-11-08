package com.spscompany.spsbrowser;

/**
 * SPS Extensions: small add-ons that run inside pages (CSS / JavaScript), managed from the Extension store.
 * Android's WebView cannot run Chrome extension packages, so these are built in or written by the user (user scripts).
 */
final class Extensions {
    static final class Def {
        final String id, name, desc, icon;
        final String[] options;          // null = no settings; otherwise labels of the choices
        final int defaultOption;
        Def(String id, String name, String desc, String icon, String[] options, int def) {
            this.id = id; this.name = name; this.desc = desc; this.icon = icon; this.options = options; this.defaultOption = def;
        }
    }

    static final Def[] CATALOG = {
            new Def("darkpages", "Dark pages", "Turns bright websites dark (images stay natural).", "dark", new String[]{"Soft", "Normal", "Strong"}, 1),
            new Def("cookiehide", "Cookie banner hider", "Hides cookie / consent pop-ups and unlocks scrolling.", "shield", null, 0),
            new Def("readable", "Comfortable reading", "Bigger text and a narrow, centred column on article pages.", "reader", new String[]{"110%", "125%", "150%", "175%"}, 1),
            new Def("copyunlock", "Copy unlock", "Lets you select and copy text on sites that block it.", "copy", null, 0),
            new Def("forcezoom", "Always allow zoom", "Pinch-to-zoom on pages that disable it.", "find", null, 0),
            new Def("cleanpage", "Clean page", "Hides sticky bars, chat bubbles and floating pop-ups.", "magic", null, 0),
            new Def("noimages", "Text only", "Hides images to save data and to read faster.", "eyeoff", null, 0),
    };

    private Extensions() { }

    static Def byId(String id) {
        for (Def d : CATALOG) if (d.id.equals(id)) return d;
        return null;
    }

    private static String css(String id, String css) {
        return "(function(){var s=document.getElementById('sps-x-" + id + "');if(!s){s=document.createElement('style');s.id='sps-x-" + id
                + "';(document.head||document.documentElement).appendChild(s);}s.textContent=" + quote(css) + ";})();";
    }

    static String quote(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c == '\n') b.append("\\n");
            else if (c == '\r') { }
            else if (c < 32) b.append(' ');
            else b.append(c);
        }
        return b.append('"').toString();
    }

    /** JavaScript for one built-in extension. option = index into Def.options. */
    static String js(String id, int option) {
        switch (id) {
            case "darkpages": {
                String f = option == 0 ? "invert(.88) hue-rotate(180deg)" : option == 2 ? "invert(1) hue-rotate(180deg) contrast(1.1)" : "invert(.94) hue-rotate(180deg)";
                String back = option == 0 ? "invert(.88) hue-rotate(180deg)" : "invert(1) hue-rotate(180deg)";
                return css(id, "html{background:#fff;filter:" + f + " !important}img,video,canvas,picture,svg image,[style*='background-image']{filter:" + back + " !important}");
            }
            case "cookiehide":
                return css(id, "#onetrust-banner-sdk,#onetrust-consent-sdk,#CybotCookiebotDialog,#cookie-banner,#cookie-notice,#cookieConsent,#gdpr-banner,"
                        + ".cookie-banner,.cookie-notice,.cookie-consent,.cc-window,.cc-banner,.qc-cmp2-container,.truste_overlay,.fc-consent-root,"
                        + "[id^='sp_message_container'],[class*='cookie-banner'],[class*='cookieBanner'],[class*='consent-banner']{display:none !important}"
                        + "html,body{overflow:auto !important;position:static !important}")
                        + "(function(){try{document.documentElement.style.overflow='auto';document.body.style.overflow='auto';}catch(e){}})();";
            case "readable": {
                int[] pct = {110, 125, 150, 175};
                int p = pct[Math.max(0, Math.min(3, option))];
                return css(id, "article,main,[role=main],.post,.entry-content,.article-body{max-width:46em !important;margin-left:auto !important;margin-right:auto !important;"
                        + "font-size:" + p + "% !important;line-height:1.7 !important}p,li{line-height:1.7 !important}");
            }
            case "copyunlock":
                return css(id, "*{-webkit-user-select:text !important;user-select:text !important}")
                        + "(function(){['copy','cut','paste','contextmenu','selectstart','dragstart'].forEach(function(t){document.addEventListener(t,function(e){e.stopImmediatePropagation();},true);});"
                        + "document.oncontextmenu=null;document.onselectstart=null;document.oncopy=null;})();";
            case "forcezoom":
                return "(function(){var m=document.querySelector('meta[name=viewport]');if(!m){m=document.createElement('meta');m.name='viewport';(document.head||document.documentElement).appendChild(m);}"
                        + "m.setAttribute('content','width=device-width,initial-scale=1,maximum-scale=10,user-scalable=yes');})();";
            case "cleanpage":
                return "(function(){function run(){try{var all=document.body?document.body.getElementsByTagName('*'):[];for(var i=0;i<all.length;i++){var e=all[i];var cs=getComputedStyle(e);"
                        + "if((cs.position==='fixed'||cs.position==='sticky')&&e.tagName!=='HTML'&&e.tagName!=='BODY'){var r=e.getBoundingClientRect();"
                        + "if(r.width*r.height<window.innerWidth*window.innerHeight*0.6&&r.height>0){e.style.setProperty('display','none','important');}}}}catch(x){}}run();setTimeout(run,1500);})();";
            case "noimages":
                return css(id, "img,picture,video,svg,canvas,[style*='background-image']{display:none !important}");
            default:
                return "";
        }
    }

    /** True when the user script's match pattern ("*", "example.com", "*.example.com") fits the host. */
    static boolean hostMatches(String pattern, String host) {
        if (pattern == null || host == null) return false;
        String p = pattern.trim().toLowerCase(java.util.Locale.ROOT), h = host.toLowerCase(java.util.Locale.ROOT);
        if (p.isEmpty() || p.equals("*")) return true;
        if (p.startsWith("*.")) { String base = p.substring(2); return h.equals(base) || h.endsWith("." + base); }
        return h.equals(p) || h.equals("www." + p);
    }
}
