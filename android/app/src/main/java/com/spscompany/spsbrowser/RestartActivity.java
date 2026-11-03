package com.spscompany.spsbrowser;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Process;

/**
 * Runs in its own process (":restart"). It ends the main process and then opens the app again, so a real restart
 * (needed when the profile's own WebView data must be opened) never leaves the user at the home screen.
 */
public class RestartActivity extends Activity {
    @SuppressWarnings("deprecation")
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Intent in = getIntent();
        int pid = in.getIntExtra("pid", -1);
        Intent next = in.getParcelableExtra("next");
        if (pid > 0 && pid != Process.myPid()) Process.killProcess(pid);
        if (next != null) {
            try { startActivity(next); } catch (Exception ignored) { }
        }
        finish();
        Runtime.getRuntime().exit(0);
    }
}
