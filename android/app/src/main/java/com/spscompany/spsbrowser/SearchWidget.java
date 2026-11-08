package com.spscompany.spsbrowser;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.widget.RemoteViews;

/** Home-screen search bar: tap = type a search, microphone = voice search, camera = search with Lens. */
public class SearchWidget extends AppWidgetProvider {
    static final String CMD = "sps_cmd";
    static final String SEARCH = "search", VOICE = "voice", LENS = "lens";

    @Override
    public void onUpdate(Context ctx, AppWidgetManager mgr, int[] ids) {
        String pkg = ctx.getPackageName();
        int layout = ctx.getResources().getIdentifier("widget_search", "layout", pkg);
        if (layout == 0) return;
        for (int id : ids) {
            RemoteViews rv = new RemoteViews(pkg, layout);
            try {                                           // a broken tap target must never stop the widget from showing
                bind(ctx, rv, "w_pill", SEARCH, 1);
                bind(ctx, rv, "w_text", SEARCH, 1);
                bind(ctx, rv, "w_search", SEARCH, 1);
                bind(ctx, rv, "w_mic", VOICE, 2);
                bind(ctx, rv, "w_lens", LENS, 3);
            } catch (Throwable ignored) { }
            try { mgr.updateAppWidget(id, rv); } catch (Throwable ignored) { }
        }
    }

    /** Asks the launcher to place the widget (Android 8+). Returns false when the launcher cannot do that. */
    static boolean requestPin(Context ctx) {
        try {
            if (Build.VERSION.SDK_INT < 26) return false;
            AppWidgetManager m = AppWidgetManager.getInstance(ctx);
            if (!m.isRequestPinAppWidgetSupported()) return false;
            return m.requestPinAppWidget(new android.content.ComponentName(ctx, SearchWidget.class), null, null);
        } catch (Throwable e) { return false; }
    }

    private static void bind(Context ctx, RemoteViews rv, String viewName, String command, int code) {
        int view = ctx.getResources().getIdentifier(viewName, "id", ctx.getPackageName());
        if (view == 0) return;
        Intent i = new Intent(ctx, MainActivity.class);
        i.setAction("com.spscompany.spsbrowser.WIDGET_" + command.toUpperCase());
        i.putExtra(CMD, command);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0);
        rv.setOnClickPendingIntent(view, PendingIntent.getActivity(ctx, code, i, flags));
    }
}
