import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("preview_builder", HERE / "build_preview.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PreviewAcceptance(unittest.TestCase):
    def test_source_string_cannot_close_json_script(self):
        attack = '</script><script>window.injected=true</script>\u2028\u2029'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output = root / "data.json", root / "preview.html"
            source.write_text(json.dumps({"schema_version":1,"mode":"test","note":attack}))
            module.build(source, output)
            html = output.read_text()
            self.assertNotIn(attack, html)
            self.assertNotIn("__CITY_DATA__", html)
            payload = html.split('<script id="city-data" type="application/json">',1)[1].split('</script>',1)[0]
            self.assertEqual(json.loads(payload)["note"], attack)

    def test_non_test_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "data.json"
            source.write_text(json.dumps({"schema_version":1,"mode":"production"}))
            with self.assertRaises(ValueError):
                module.build(source, root / "preview.html")


if __name__ == "__main__":
    unittest.main()
