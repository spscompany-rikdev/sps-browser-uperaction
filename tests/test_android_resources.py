"""Poor man's aapt: every @drawable/@layout/@string/@style/@anim/@xml reference in the Android resources and the manifest must exist."""
import glob, os, re, unittest
import xml.dom.minidom as minidom

RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "android", "app", "src", "main", "res")
MAN = os.path.join(os.path.dirname(RES), "AndroidManifest.xml")


def defined():
    d = {k: set() for k in ("drawable", "layout", "string", "style", "anim", "xml", "mipmap", "color", "id")}
    for f in glob.glob(RES + "/**/*", recursive=True):
        if os.path.isfile(f):
            folder = os.path.basename(os.path.dirname(f)).split("-")[0]
            if folder in d:
                d[folder].add(os.path.splitext(os.path.basename(f))[0])
    for f in glob.glob(RES + "/values*/*.xml"):
        dom = minidom.parse(f)
        for tag, kind in (("string", "string"), ("style", "style"), ("color", "color")):
            for n in dom.getElementsByTagName(tag):
                d[kind].add(n.getAttribute("name"))
    for f in glob.glob(RES + "/layout*/*.xml"):
        d["id"] |= set(re.findall(r'@\+id/(\w+)', open(f, encoding="utf-8").read()))
    return d


class ResourceTests(unittest.TestCase):
    def test_all_xml_parse(self):
        for f in glob.glob(RES + "/**/*.xml", recursive=True) + [MAN]:
            minidom.parse(f)

    def test_references_resolve(self):
        d = defined()
        # created by the build itself (gradle resValue) - not a file
        d["string"].add("update_repo")
        bad = []
        for f in glob.glob(RES + "/**/*.xml", recursive=True) + [MAN]:
            text = open(f, encoding="utf-8").read()
            for kind, name in re.findall(r'@(drawable|layout|string|style|anim|xml|mipmap|color)/([\w.]+)', text):
                name = name.replace(".", "_") if kind == "style" else name
                if name not in d[kind]:
                    bad.append("%s: @%s/%s" % (os.path.basename(f), kind, name))
        self.assertEqual(bad, [])

    def test_widget_uses_only_remoteviews_classes(self):
        allowed = {"LinearLayout", "FrameLayout", "RelativeLayout", "TextView", "ImageView", "Button", "ImageButton", "ProgressBar", "GridLayout"}
        text = open(os.path.join(RES, "layout", "widget_search.xml"), encoding="utf-8").read()
        used = set(re.findall(r"<(\w+)", text))
        self.assertTrue(used <= allowed, used - allowed)
        self.assertNotIn(".xml", "".join(os.listdir(os.path.join(RES, "drawable-nodpi"))))   # widget icons are plain PNGs (no vector inflation in the launcher)


if __name__ == "__main__":
    unittest.main()
