package com.spscompany.spsbrowser;

import java.security.SecureRandom;

/** Strong password generator (SecureRandom) and a simple strength estimate. */
final class PasswordGen {
    private static final SecureRandom RNG = new SecureRandom();
    private static final String UP = "ABCDEFGHJKLMNPQRSTUVWXYZ", UP_AMB = "IO";
    private static final String LOW = "abcdefghijkmnopqrstuvwxyz", LOW_AMB = "l";
    private static final String DIG = "23456789", DIG_AMB = "01";
    private static final String SYM = "!@#$%^&*-_=+?.:;";
    private static final String[] WORDS = ("able acid aged also area army away baby back ball band bank base bath bear beat bell belt best bird blue boat body bone book boom born both bowl "
            + "bulb burn cafe cake calm came camp card care cart case cash cast cell chat chef chip city clay clip club coal coat code coin cold come cook cool copy cord core "
            + "corn cost crew crop dark data date dawn deal deep deer desk dial dice diet dish dive dock door dove down draw drum duck dust duty each earn east easy edge else "
            + "epic even ever exam face fact fair fall farm fast fate fern file film find fine fire fish five flag flat flow foam fold folk food foot form fort four free frog "
            + "fuel full fund gain game gate gear gift girl glad glow goal gold golf good gown grab gray grid grow gulf hair half hall hand hard harp hawk heal heat help herb "
            + "hero hill hint hold home hope horn host huge hunt idea inch iron isle jade jazz join joke jump june keen keep kind king kite knee lake lamp land lane last lava "
            + "leaf lean left lens life lift lime line lion list live load lock loft long loop lost loud love luck lump lunch lynx made mail main make male many maps mark mask "
            + "mate maze meal meet melt menu mesh mild mile milk mind mine mint miss mode moon more moss move much music name navy neat nest news next nice nine node noon note "
            + "oak oasis ocean omit once only open opal orbit otter oval oven pack page pair palm park part pass path peak pear peel pine pink pipe plan play plum pond pony pool "
            + "port post pour pure quartz quick quiet quit race rail rain rank rare read real reed rest rice rich ride ring rise road rock roof room root rope rose ruby rule "
            + "safe sage sail salt sand save seal seed self sell shed ship shoe shop show side sign silk silver sing site skin sky slim slow snow soft soil solo song soon "
            + "sort soul soup span spin spot star stay stem step stone stop swan swim tail take tale tall tank tape task team tent test text thin tide tile time tiny tone tool "
            + "town trail tree trip true tube tune turn twin unit upon urban vast vest view vine visit voice wait walk wall warm wave wild wind wing wise wolf wood wool word "
            + "work yard year yoga zero zone").split(" ");

    private PasswordGen() { }

    static String random(int len, boolean upper, boolean lower, boolean digits, boolean symbols, boolean noAmbiguous) {
        StringBuilder pool = new StringBuilder();
        java.util.ArrayList<String> sets = new java.util.ArrayList<>();
        if (upper) { String s = UP + (noAmbiguous ? "" : UP_AMB); sets.add(s); pool.append(s); }
        if (lower) { String s = LOW + (noAmbiguous ? "" : LOW_AMB); sets.add(s); pool.append(s); }
        if (digits) { String s = DIG + (noAmbiguous ? "" : DIG_AMB); sets.add(s); pool.append(s); }
        if (symbols) { sets.add(SYM); pool.append(SYM); }
        if (pool.length() == 0) { sets.add(LOW); pool.append(LOW); }
        len = Math.max(len, sets.size());
        char[] out = new char[len];
        for (int i = 0; i < len; i++) out[i] = pool.charAt(RNG.nextInt(pool.length()));
        for (int i = 0; i < sets.size() && i < len; i++) {            // make sure every chosen kind appears at least once
            String s = sets.get(i);
            out[i] = s.charAt(RNG.nextInt(s.length()));
        }
        for (int i = len - 1; i > 0; i--) {                            // shuffle so the guaranteed characters are not always first
            int j = RNG.nextInt(i + 1);
            char t = out[i]; out[i] = out[j]; out[j] = t;
        }
        return new String(out);
    }

    static String words(int count, boolean capitalize, boolean number) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < count; i++) {
            String w = WORDS[RNG.nextInt(WORDS.length)];
            if (capitalize) w = Character.toUpperCase(w.charAt(0)) + w.substring(1);
            if (i > 0) sb.append('-');
            sb.append(w);
        }
        if (number) sb.append('-').append(10 + RNG.nextInt(90));
        return sb.toString();
    }

    /** Rough entropy in bits (0..~130). */
    static double bits(String p) {
        if (p == null || p.isEmpty()) return 0;
        boolean u = false, l = false, d = false, s = false;
        java.util.HashSet<Character> uniq = new java.util.HashSet<>();
        for (char ch : p.toCharArray()) {
            uniq.add(ch);
            if (Character.isUpperCase(ch)) u = true; else if (Character.isLowerCase(ch)) l = true;
            else if (Character.isDigit(ch)) d = true; else s = true;
        }
        int pool = (u ? 26 : 0) + (l ? 26 : 0) + (d ? 10 : 0) + (s ? 30 : 0);
        double b = p.length() * (Math.log(Math.max(pool, 2)) / Math.log(2));
        double variety = uniq.size() / (double) p.length();            // aaaaaaaa is weak even if long
        if (variety < 0.5) b *= variety + 0.3;
        String low = p.toLowerCase();
        for (String bad : new String[]{"password", "qwerty", "123456", "letmein", "admin", "welcome", "iloveyou", "abc123"})
            if (low.contains(bad)) b = Math.min(b, 20);
        return b;
    }

    static int level(String p) {                                       // 0 weak, 1 fair, 2 good, 3 strong
        double b = bits(p);
        return b < 40 ? 0 : b < 60 ? 1 : b < 80 ? 2 : 3;
    }

    static String levelName(int lv) {
        return new String[]{"Weak", "Fair", "Good", "Strong"}[lv];
    }

    static int levelColor(int lv) {
        return new int[]{UI.DANGER, 0xFFE37400, 0xFF1A73E8, UI.OK}[lv];
    }
}
