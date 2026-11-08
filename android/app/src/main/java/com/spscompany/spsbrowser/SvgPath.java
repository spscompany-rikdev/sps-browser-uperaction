package com.spscompany.spsbrowser;

import java.util.ArrayList;
import java.util.List;

/**
 * Tiny SVG path-data parser (pure Java, no Android classes, unit-testable on a PC).
 * Supports M m L l H h V v C c S s Q q T t A a Z z. Every command is converted to absolute
 * MOVE (0), LINE (1), CUBIC (2) or CLOSE (3) operations; arcs become cubic Bezier curves.
 * Result: float[][] where op[0] is the type followed by its coordinates.
 */
final class SvgPath {
    static final int MOVE = 0, LINE = 1, CUBIC = 2, CLOSE = 3;

    private final String s;
    private int i;

    private SvgPath(String s) { this.s = s; }

    static float[][] parse(String d) {
        if (d == null) return new float[0][];
        return new SvgPath(d).run();
    }

    private void ws() {
        while (i < s.length() && (s.charAt(i) == ' ' || s.charAt(i) == ',' || s.charAt(i) == '\n' || s.charAt(i) == '\t' || s.charAt(i) == '\r')) i++;
    }

    private boolean hasNum() {
        ws();
        if (i >= s.length()) return false;
        char c = s.charAt(i);
        return c == '-' || c == '+' || c == '.' || (c >= '0' && c <= '9');
    }

    private float num() {
        ws();
        int st = i;
        if (i < s.length() && (s.charAt(i) == '-' || s.charAt(i) == '+')) i++;
        boolean dot = false;
        while (i < s.length()) {
            char c = s.charAt(i);
            if (c >= '0' && c <= '9') i++;
            else if (c == '.' && !dot) { dot = true; i++; }
            else if ((c == 'e' || c == 'E') && i + 1 < s.length() && (Character.isDigit(s.charAt(i + 1)) || s.charAt(i + 1) == '-')) { i += 2; }
            else break;
        }
        if (st == i) throw new IllegalArgumentException("number expected at " + i);
        return Float.parseFloat(s.substring(st, i));
    }

    private boolean flag() {            // arc flags may be glued together ("a1 1 0 011 1")
        ws();
        char c = s.charAt(i++);
        return c == '1';
    }

    private float[][] run() {
        List<float[]> out = new ArrayList<>();
        float cx = 0, cy = 0, sx = 0, sy = 0, lcx = 0, lcy = 0;   // current, subpath start, last control point
        char cmd = 0, prev = 0;
        while (true) {
            ws();
            if (i >= s.length()) break;
            char c = s.charAt(i);
            if (Character.isLetter(c)) { cmd = c; i++; } else if (cmd == 0) throw new IllegalArgumentException("bad path");
            boolean rel = Character.isLowerCase(cmd);
            char up = Character.toUpperCase(cmd);
            if (up == 'Z') {
                out.add(new float[]{CLOSE}); cx = sx; cy = sy; prev = 'Z'; continue;
            }
            if (!hasNum()) { if (i >= s.length()) break; throw new IllegalArgumentException("number expected"); }
            switch (up) {
                case 'M': {
                    float x = num(), y = num();
                    if (rel) { x += cx; y += cy; }
                    out.add(new float[]{MOVE, x, y}); cx = sx = x; cy = sy = y;
                    cmd = rel ? 'l' : 'L';                           // extra pairs are line-tos
                    break;
                }
                case 'L': {
                    float x = num(), y = num();
                    if (rel) { x += cx; y += cy; }
                    out.add(new float[]{LINE, x, y}); cx = x; cy = y; break;
                }
                case 'H': { float x = num(); if (rel) x += cx; out.add(new float[]{LINE, x, cy}); cx = x; break; }
                case 'V': { float y = num(); if (rel) y += cy; out.add(new float[]{LINE, cx, y}); cy = y; break; }
                case 'C': case 'S': {
                    float x1, y1;
                    if (up == 'C') {
                        x1 = num(); y1 = num();
                        if (rel) { x1 += cx; y1 += cy; }
                    } else {
                        boolean pc = prev == 'C' || prev == 'S';
                        x1 = pc ? 2 * cx - lcx : cx; y1 = pc ? 2 * cy - lcy : cy;
                    }
                    float x2 = num(), y2 = num(), x = num(), y = num();
                    if (rel) { x2 += cx; y2 += cy; x += cx; y += cy; }
                    out.add(new float[]{CUBIC, x1, y1, x2, y2, x, y});
                    lcx = x2; lcy = y2; cx = x; cy = y; break;
                }
                case 'Q': case 'T': {
                    float qx, qy;
                    if (up == 'Q') {
                        qx = num(); qy = num();
                        if (rel) { qx += cx; qy += cy; }
                    } else {
                        boolean pq = prev == 'Q' || prev == 'T';
                        qx = pq ? 2 * cx - lcx : cx; qy = pq ? 2 * cy - lcy : cy;
                    }
                    float x = num(), y = num();
                    if (rel) { x += cx; y += cy; }
                    out.add(new float[]{CUBIC, cx + 2f / 3f * (qx - cx), cy + 2f / 3f * (qy - cy), x + 2f / 3f * (qx - x), y + 2f / 3f * (qy - y), x, y});
                    lcx = qx; lcy = qy; cx = x; cy = y; break;
                }
                case 'A': {
                    float rx = num(), ry = num(), rot = num();
                    boolean large = flag(), sweep = flag();
                    float x = num(), y = num();
                    if (rel) { x += cx; y += cy; }
                    arc(out, cx, cy, rx, ry, rot, large, sweep, x, y);
                    cx = x; cy = y; break;
                }
                default:
                    throw new IllegalArgumentException("unknown command " + cmd);
            }
            prev = up;
        }
        return out.toArray(new float[0][]);
    }

    /** SVG elliptical arc -> cubic Beziers (endpoint to centre parametrisation, W3C implementation notes F.6). */
    private static void arc(List<float[]> out, float x0, float y0, float rx, float ry, float rotDeg, boolean large, boolean sweep, float x, float y) {
        if (x0 == x && y0 == y) return;
        rx = Math.abs(rx); ry = Math.abs(ry);
        if (rx == 0 || ry == 0) { out.add(new float[]{LINE, x, y}); return; }
        double phi = Math.toRadians(rotDeg), cp = Math.cos(phi), sp = Math.sin(phi);
        double dx = (x0 - x) / 2.0, dy = (y0 - y) / 2.0;
        double x1 = cp * dx + sp * dy, y1 = -sp * dx + cp * dy;
        double lam = (x1 * x1) / ((double) rx * rx) + (y1 * y1) / ((double) ry * ry);
        if (lam > 1) { double sq = Math.sqrt(lam); rx *= sq; ry *= sq; }
        double rx2 = (double) rx * rx, ry2 = (double) ry * ry;
        double num = rx2 * ry2 - rx2 * y1 * y1 - ry2 * x1 * x1;
        double den = rx2 * y1 * y1 + ry2 * x1 * x1;
        double co = Math.sqrt(Math.max(0, num / den)) * (large == sweep ? -1 : 1);
        double cxp = co * rx * y1 / ry, cyp = -co * ry * x1 / rx;
        double ccx = cp * cxp - sp * cyp + (x0 + x) / 2.0, ccy = sp * cxp + cp * cyp + (y0 + y) / 2.0;
        double th1 = Math.atan2((y1 - cyp) / ry, (x1 - cxp) / rx);
        double th2 = Math.atan2((-y1 - cyp) / ry, (-x1 - cxp) / rx);
        double dth = th2 - th1;
        if (sweep && dth < 0) dth += 2 * Math.PI;
        else if (!sweep && dth > 0) dth -= 2 * Math.PI;
        int n = (int) Math.ceil(Math.abs(dth) / (Math.PI / 2) - 1e-9);
        if (n < 1) n = 1;
        double step = dth / n, t = 4.0 / 3.0 * Math.tan(step / 4);
        double a = th1;
        for (int k = 0; k < n; k++) {
            double a2 = a + step;
            double c1x = Math.cos(a) - t * Math.sin(a), c1y = Math.sin(a) + t * Math.cos(a);
            double c2x = Math.cos(a2) + t * Math.sin(a2), c2y = Math.sin(a2) - t * Math.cos(a2);
            double ex = Math.cos(a2), ey = Math.sin(a2);
            out.add(new float[]{CUBIC, tx(c1x, c1y, rx, ry, cp, sp, ccx), ty(c1x, c1y, rx, ry, cp, sp, ccy),
                    tx(c2x, c2y, rx, ry, cp, sp, ccx), ty(c2x, c2y, rx, ry, cp, sp, ccy),
                    k == n - 1 ? x : tx(ex, ey, rx, ry, cp, sp, ccx), k == n - 1 ? y : ty(ex, ey, rx, ry, cp, sp, ccy)});
            a = a2;
        }
    }

    private static float tx(double ux, double uy, double rx, double ry, double cp, double sp, double cx) { return (float) (cp * rx * ux - sp * ry * uy + cx); }
    private static float ty(double ux, double uy, double rx, double ry, double cp, double sp, double cy) { return (float) (sp * rx * ux + cp * ry * uy + cy); }
}
