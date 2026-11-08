package com.spscompany.spsbrowser;

import java.net.URLEncoder;

/** "Search with Lens": builds the little page that uploads a photo to Google Lens (a normal multipart form post made by the browser). */
final class Lens {
    static final String UPLOAD = "https://lens.google.com/v3/upload";
    static final String FIELD = "encoded_image";

    private Lens() { }

    /** Lens for an image that is already on the web (long-press an image). */
    static String byUrl(String imageUrl) {
        try { return "https://lens.google.com/uploadbyurl?url=" + URLEncoder.encode(imageUrl, "UTF-8"); }
        catch (Exception e) { return "https://lens.google.com/"; }
    }

    /** A page that turns the Base64 JPEG into a file and posts it to Lens straight away. */
    static String uploadPage(String action, String field, String b64) {
        return "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;color:#5f6368;background:#fff}</style></head>"
                + "<body><div id='m'>Searching with Lens...</div>"
                + "<form id='f' method='POST' enctype='multipart/form-data' action='" + action + "' style='display:none'>"
                + "<input type='file' name='" + field + "' id='i'></form>"
                + "<script>(function(){try{var b=atob('" + b64 + "');var a=new Uint8Array(b.length);for(var k=0;k<b.length;k++)a[k]=b.charCodeAt(k);"
                + "var file=new File([a],'photo.jpg',{type:'image/jpeg'});var dt=new DataTransfer();dt.items.add(file);"
                + "document.getElementById('i').files=dt.files;document.getElementById('f').submit();}"
                + "catch(e){document.getElementById('m').textContent='Could not start the search: '+e;}})();</script></body></html>";
    }
}
