package com.spscompany.spsbrowser;

import java.util.Calendar;

/** Short, widely quoted sayings of well-known people (shown as "thought of the day"; wording as commonly published). */
final class Quotes {
    static final String[][] LIST = {
            {"Dream, dream, dream. Dreams transform into thoughts and thoughts result in action.", "A. P. J. Abdul Kalam"},
            {"Arise, awake, and stop not till the goal is reached.", "Swami Vivekananda"},
            {"You can't cross the sea merely by standing and staring at the water.", "Rabindranath Tagore"},
            {"Education is the most powerful weapon which you can use to change the world.", "Nelson Mandela"},
            {"Imagination is more important than knowledge.", "Albert Einstein"},
            {"Stay hungry, stay foolish.", "Steve Jobs"},
            {"Nothing in life is to be feared, it is only to be understood.", "Marie Curie"},
            {"It does not matter how slowly you go as long as you do not stop.", "Confucius"},
            {"The only way to do great work is to love what you do.", "Steve Jobs"},
            {"I have not failed. I've just found 10,000 ways that won't work.", "Thomas Edison"},
            {"Be less curious about people and more curious about ideas.", "Marie Curie"},
            {"Genius is one percent inspiration and ninety-nine percent perspiration.", "Thomas Edison"},
    };

    private Quotes() { }

    static int today() {
        Calendar c = Calendar.getInstance();
        return (c.get(Calendar.YEAR) * 366 + c.get(Calendar.DAY_OF_YEAR)) % LIST.length;
    }

    static String[] at(int i) {
        return LIST[((i % LIST.length) + LIST.length) % LIST.length];
    }
}
