package com.spscompany.spsbrowser;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.HashMap;
import java.util.Map;

/**
 * Crisp vector icons drawn with Canvas (no image files). The shapes live in assets/icons.txt as tiny path programs on a 24x24 grid:
 * M x,y  L x,y  Z   (outline path)   N x,y (filled path)   C cx,cy,r (circle)   F cx,cy,r (filled circle)
 * A cx,cy,r,start,sweep (arc)   R x,y,w,h,radius (rounded rectangle)
 */
final class Ico extends Drawable {
    private static final Map<String, String> DEFS = new HashMap<>();
    private final String[] toks;
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);

    static void load(Context c) {
        if (!DEFS.isEmpty()) return;
        try (BufferedReader r = new BufferedReader(new InputStreamReader(c.getAssets().open("icons.txt"), "UTF-8"))) {
            String line;
            while ((line = r.readLine()) != null) {
                int i = line.indexOf('|');
                if (i > 0) DEFS.put(line.substring(0, i), line.substring(i + 1));
            }
        } catch (Exception ignored) { }
    }

    static Ico of(String name, int color) {
        String d = DEFS.get(name);
        return new Ico(d == null ? "" : d, color);
    }

    private Ico(String def, int color) {
        toks = def.trim().isEmpty() ? new String[0] : def.trim().split("\\s+");
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeCap(Paint.Cap.ROUND);
        stroke.setStrokeJoin(Paint.Join.ROUND);
        stroke.setStrokeWidth(2f);
        fill.setStyle(Paint.Style.FILL);
        setColor(color);
    }

    Ico setColor(int color) {
        stroke.setColor(color);
        fill.setColor(color);
        invalidateSelf();
        return this;
    }

    private static float[] nums(String s) {
        String[] p = s.split(",");
        float[] f = new float[p.length];
        for (int i = 0; i < p.length; i++) f[i] = Float.parseFloat(p[i]);
        return f;
    }

    @Override
    public void draw(Canvas canvas) {
        android.graphics.Rect b = getBounds();
        if (b.isEmpty()) return;
        canvas.save();
        canvas.translate(b.left, b.top);
        canvas.scale(b.width() / 24f, b.height() / 24f);
        Path path = new Path();
        boolean filled = false;
        String prev = "";
        try {
            for (int i = 0; i < toks.length; i++) {
                String t = toks[i];
                if (t.equals("Z")) {
                    path.close();
                    flush(canvas, path, filled);
                    path = new Path();
                    prev = t;
                    continue;
                }
                String a = i + 1 < toks.length ? toks[++i] : "";
                float[] v = nums(a);
                switch (t) {
                    case "M": case "N":
                        flush(canvas, path, filled);
                        path = new Path();
                        filled = t.equals("N");
                        path.moveTo(v[0], v[1]);
                        break;
                    case "L":
                        path.lineTo(v[0], v[1]);
                        break;
                    case "C":
                        flush(canvas, path, filled);
                        path = new Path();
                        canvas.drawCircle(v[0], v[1], v[2], stroke);
                        break;
                    case "F":
                        flush(canvas, path, filled);
                        path = new Path();
                        canvas.drawCircle(v[0], v[1], v[2], fill);
                        break;
                    case "A": {
                        boolean connect = prev.equals("M") || prev.equals("L");
                        if (!connect) { flush(canvas, path, filled); path = new Path(); filled = false; }
                        path.arcTo(new RectF(v[0] - v[2], v[1] - v[2], v[0] + v[2], v[1] + v[2]), v[3], v[4], !connect);
                        break;
                    }
                    case "R":
                        flush(canvas, path, filled);
                        path = new Path();
                        canvas.drawRoundRect(new RectF(v[0], v[1], v[0] + v[2], v[1] + v[3]), v[4], v[4], stroke);
                        break;
                    default:
                        break;
                }
                prev = t;
            }
            flush(canvas, path, filled);
        } catch (RuntimeException ignored) { }
        canvas.restore();
    }

    private void flush(Canvas c, Path p, boolean filled) {
        if (p.isEmpty()) return;
        c.drawPath(p, filled ? fill : stroke);
    }

    @Override public void setAlpha(int alpha) { stroke.setAlpha(alpha); fill.setAlpha(alpha); }
    @Override public void setColorFilter(ColorFilter cf) { stroke.setColorFilter(cf); fill.setColorFilter(cf); }
    @Override public int getOpacity() { return PixelFormat.TRANSLUCENT; }
}
