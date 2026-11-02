package com.spscompany.spsbrowser;

import android.app.Activity;
import android.view.View;

/** What the pages (bookmarks, history, tabs, passwords ...) may ask the browser window to do. */
interface Host {
    Activity act();
    Store store();
    void open(String url, boolean newTab);
    void push(View page);
    void pop();
    void toast(String s);
    /** Runs ok after the phone's screen lock (PIN / pattern / fingerprint) was confirmed; protects saved passwords. */
    void unlock(Runnable ok);
    /** Copies text that is cleared from the clipboard again after 30 seconds. */
    void copySecret(String text);
    void share(String text);
}

/** A full-screen page that handles the Back button itself. */
interface Page {
    /** @return true when Back was used up (for example closing a search box); false to close the page. */
    boolean onBack();
}
