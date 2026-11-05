package com.spscompany.spsbrowser;

import android.graphics.Bitmap;
import android.graphics.Color;

import io.nayuki.qrcodegen.QrCode;

/** QR codes: drawing (Nayuki's MIT-licensed generator) and the page that decodes a photo with jsQR (Apache-2.0) inside a hidden WebView. */
final class Qr {
    private Qr() { }

    static final int MAX_BYTES = 1800;

    static boolean[][] modules(String text) {
        QrCode q = QrCode.encodeText(text, QrCode.Ecc.MEDIUM);
        boolean[][] m = new boolean[q.size][q.size];
        for (int y = 0; y < q.size; y++) for (int x = 0; x < q.size; x++) m[y][x] = q.getModule(x, y);
        return m;
    }

    static Bitmap bitmap(String text, int px) {
        boolean[][] m = modules(text);
        int border = 4, n = m.length + 2 * border, cell = Math.max(2, px / n);
        Bitmap b = Bitmap.createBitmap(cell * n, cell * n, Bitmap.Config.ARGB_8888);
        b.eraseColor(Color.WHITE);
        for (int y = 0; y < m.length; y++)
            for (int x = 0; x < m.length; x++)
                if (m[y][x]) for (int dy = 0; dy < cell; dy++) for (int dx = 0; dx < cell; dx++) b.setPixel((x + border) * cell + dx, (y + border) * cell + dy, Color.BLACK);
        return b;
    }

    /** HTML that decodes the JPEG (base64) and reports the text through window.SPSQR.result(text-or-empty). */
    static String decodePage(String jsQrSource, String jpegBase64) {
        return "<html><body><canvas id=c></canvas><script>" + jsQrSource.replace("</script", "<\\/script") + "</script><script>"
                + "(function(){var img=new Image();img.onload=function(){try{var c=document.getElementById('c');c.width=img.width;c.height=img.height;"
                + "var x=c.getContext('2d');x.drawImage(img,0,0);var r=jsQR(x.getImageData(0,0,c.width,c.height).data,c.width,c.height,{inversionAttempts:'attemptBoth'});"
                + "SPSQR.result(r?r.data:'');}catch(e){SPSQR.result('');}};img.onerror=function(){SPSQR.result('');};"
                + "img.src='data:image/jpeg;base64," + jpegBase64 + "';})();</script></body></html>";
    }

    /** Only web links are opened from a scan; everything else is shown as text. */
    static boolean isWebLink(String s) {
        if (s == null) return false;
        String t = s.trim().toLowerCase(java.util.Locale.US);
        return (t.startsWith("https://") || t.startsWith("http://")) && !t.contains(" ") && !t.contains("\n");
    }
}
