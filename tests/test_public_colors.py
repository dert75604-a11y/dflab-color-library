#!/usr/bin/env python3
"""Fixture-mode tests for the Feishu 公开上架 export. No network."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import feishu_public_colors as sync  # noqa: E402
import patch_nfc_index as patch  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "feishu-records.json"
SECRET = "内部备注勿出网-配方克数"
JPEG = b"\xff\xd8\xff\xd9"


class ClassifyTests(unittest.TestCase):
    def setUp(self):
        self.allowed = set(sync.DEFAULT_STATUS_ALLOW)
        self.records = sync.load_fixture(FIXTURE)

    def test_unchecked_test_row_is_not_public(self):
        reason, prepared = sync.classify(self.records[0], self.allowed)
        self.assertEqual(reason, "not_public")
        self.assertIsNone(prepared)
        self.assertEqual(sync.as_text(sync.fields_of(self.records[0]).get("code")), "F-TEST01")
        self.assertFalse(sync.as_bool(sync.fields_of(self.records[0]).get("公开上架")))

    def test_checked_test_row_fails_code_format(self):
        reason, _prepared = sync.classify(self.records[1], self.allowed)
        self.assertEqual(reason, "code_format")

    def test_hex_and_code_normalized(self):
        _reason, prepared = sync.classify(self.records[2], self.allowed)
        self.assertEqual(prepared["code"], "F-00042")
        self.assertEqual(prepared["color"], "#C4A574")
        self.assertEqual(prepared["tags"], ["橡木", "开放漆"])

    def test_lowercase_code_and_default_uploader(self):
        _reason, prepared = sync.classify(self.records[-1], self.allowed)
        self.assertEqual(prepared["code"], "F-00046")
        self.assertEqual(prepared["uploader"], "DF-LAB")
        self.assertEqual(prepared["color"], "")

    def test_rich_text_and_checkbox_shapes(self):
        record = {
            "fields": {
                "code": [{"text": "F-00007", "type": "text"}],
                "name": [{"text": "柚"}, {"text": "木色"}],
                "finish": "开放漆",
                "树种": {"text": "柚木"},
                "状态": "终板通过",
                "公开上架": ["true"],
                "主图": {"file_token": "boxcn", "name": "a.jpg"},
                "备注": SECRET,
            }
        }
        reason, prepared = sync.classify(record, self.allowed)
        self.assertIsNone(reason)
        self.assertEqual(prepared["code"], "F-00007")
        self.assertEqual(prepared["name"], "柚木色")
        self.assertEqual(prepared["species"], "柚木")


class SyncTests(unittest.TestCase):
    def test_fixture_publish_shape_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            colors, report = self._sync(dest, sync.load_fixture(FIXTURE))
            catalog = json.loads(colors.read_text(encoding="utf-8"))
            codes = [item["code"] for item in catalog]
            self.assertEqual(codes, ["F-00042", "F-00046"])
            self.assertNotIn("F-TEST01", codes)
            published = catalog[0]
            self.assertEqual(
                list(published.keys()),
                ["code", "name", "color", "finish", "species", "image", "imageCloseup", "uploader", "tags"],
            )
            self.assertEqual(published["image"], "/assets/colors/F-00042.jpg")
            self.assertEqual(published["imageCloseup"], "/assets/colors/F-00042-macro.png")
            self.assertNotIn("备注", published)
            self.assertNotIn("base64", json.dumps(catalog))
            self.assertNotIn("data:image", json.dumps(catalog))
            blob = json.dumps(catalog, ensure_ascii=False) + json.dumps(report, ensure_ascii=False)
            self.assertNotIn(SECRET, blob)
            self.assertTrue((dest / "assets" / "colors" / "F-00042.jpg").read_bytes().startswith(b"\xff\xd8"))
            self.assertFalse((dest / "assets" / "colors" / "F-00046-macro.jpg").exists())
            pairs = [(row["code"], row["reason"]) for row in report["skipped"]]
            self.assertIn(("F-TEST01", "not_public"), pairs)
            self.assertIn(("F-TEST01", "code_format"), pairs)
            self.assertEqual(pairs.count(("F-TEST01", "not_public")), 1)
            self.assertIn(("F-00043", "finish"), pairs)
            self.assertIn(("F-00044", "status"), pairs)
            self.assertIn(("F-00045", "image"), pairs)
            self.assertIn(("F-00042", "duplicate"), pairs)
            self.assertIn("rec_ok", report["writeback_record_ids"])
            self.assertNotIn("rec_listed", report["writeback_record_ids"])
            self.assertNotIn("rec_test_unchecked", report["writeback_record_ids"])

    def test_uncheck_removes_card_and_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            image_dir = dest / "assets" / "colors"
            image_dir.mkdir(parents=True)
            (image_dir / "F-00099.jpg").write_bytes(JPEG)
            (image_dir / "notes.txt").write_text("keep", encoding="utf-8")
            self._sync(dest, sync.load_fixture(FIXTURE))
            self.assertFalse((image_dir / "F-00099.jpg").exists())
            self.assertEqual((image_dir / "notes.txt").read_text(encoding="utf-8"), "keep")
            only_hidden = [sync.load_fixture(FIXTURE)[0]]
            colors, report = self._sync(dest, only_hidden)
            catalog = json.loads(colors.read_text(encoding="utf-8"))
            self.assertEqual(catalog, [])
            self.assertEqual(report["skipped"][0]["reason"], "not_public")
            self.assertFalse((image_dir / "F-00042.jpg").exists())
            self.assertEqual((image_dir / "notes.txt").read_text(encoding="utf-8"), "keep")

    def test_bad_image_skips_row(self):
        record = {
            "record_id": "rec_bad_img",
            "fields": {
                "code": "F-00077",
                "name": "坏图",
                "finish": "开放漆",
                "状态": "终板通过",
                "公开上架": True,
                "主图": [{"name": "a.jpg", "file_token": "x"}],
            },
        }

        def fetch(_attachment):
            return b'{"code":999}'

        with tempfile.TemporaryDirectory() as tmp:
            _colors, report = sync.sync([record], Path(tmp), fetch, set(sync.DEFAULT_STATUS_ALLOW))
            self.assertEqual(report["published"], [])
            self.assertEqual(report["skipped"][0]["reason"], "image_download")
            self.assertNotIn(SECRET, json.dumps(report, ensure_ascii=False))

    def _sync(self, dest, records):
        def fetch(attachment):
            path = ROOT / attachment["local_path"]
            blob = path.read_bytes()
            if not sync.looks_like_image(blob):
                raise RuntimeError("not image")
            return blob

        return sync.sync(records, dest, fetch, set(sync.DEFAULT_STATUS_ALLOW))


class CliTests(unittest.TestCase):
    def test_dry_run_writes_nothing_and_hides_test_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = sync.main(
                    ["sync", "--fixture", str(FIXTURE), "--dry-run", "--out-dir", str(out)]
                )
            self.assertEqual(code, 0, stderr.getvalue())
            self.assertFalse((out / "data" / "colors.json").exists())
            printed = stdout.getvalue()
            self.assertNotIn("F-TEST01", printed)
            self.assertNotIn(SECRET, printed)
            self.assertIn("F-00042", printed)
            self.assertNotIn("data:image", printed)

    def test_missing_credentials(self):
        saved = {}
        for key in list(os.environ):
            if key.startswith("FEISHU_"):
                saved[key] = os.environ.pop(key)
        try:
            code = sync.main(["sync"])
        finally:
            os.environ.update(saved)
        self.assertEqual(code, 2)

    def test_fixture_cli_matches_contract(self):
        swatch = ROOT / "tests" / "fixtures" / "swatch.jpg"
        if not swatch.exists():
            swatch.write_bytes(JPEG)
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "feishu_public_colors.py"),
                    "sync",
                    "--fixture",
                    str(FIXTURE),
                    "--out-dir",
                    tmp,
                    "--writeback-status",
                ],
                cwd=str(ROOT),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("writeback skipped", proc.stderr)
            catalog = json.loads((Path(tmp) / "data" / "colors.json").read_text(encoding="utf-8"))
            self.assertEqual([item["code"] for item in catalog], ["F-00042", "F-00046"])
            self.assertNotIn(SECRET, Path(tmp).joinpath("data", "colors.json").read_text(encoding="utf-8"))


class PatchAndDeployTests(unittest.TestCase):
    def test_patch_is_idempotent_and_keeps_gesture(self):
        html = (ROOT / "tests" / "fixtures" / "nfc-snippet.html").read_text(encoding="utf-8")
        once = patch.patch_html(html)
        twice = patch.patch_html(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.count("nfc-public-colors.js"), 1)
        self.assertIn("沪ICP备2026039729号-1", once)
        self.assertIn("上海·DF-LAB 色彩数据库", once)
        self.assertIn("gesture polish", once)
        self.assertIn("do-not-rewrite", once)
        self.assertLess(once.index("gesture polish"), once.index("nfc-public-colors.js"))

    def test_patch_refuses_legacy_browser(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            patch.patch_html(html)

    def test_local_deploy_does_not_replace_nfc_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "www"
            asset = dest / "nfc-scroll-assets"
            asset.mkdir(parents=True)
            (asset / "img-00.jpg").write_text("KEEP-ASSET", encoding="utf-8")
            (dest / "index.html").write_text(
                (ROOT / "tests" / "fixtures" / "nfc-snippet.html").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "DEPLOY_LOCAL": "1",
                    "DEPLOY_LOCAL_DIR": str(dest),
                    "PATCH_NFC": "1",
                }
            )
            proc = subprocess.run(
                ["bash", str(ROOT / "tools" / "deploy_public_colors.sh")],
                cwd=str(ROOT),
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            index = (dest / "index.html").read_text(encoding="utf-8")
            self.assertIn("assets/nfc-public-colors.js", index)
            self.assertIn("gesture polish", index)
            self.assertIn("沪ICP备2026039729号-1", index)
            self.assertEqual((asset / "img-00.jpg").read_text(encoding="utf-8"), "KEEP-ASSET")
            self.assertEqual((dest / "data" / "colors.json").read_text(encoding="utf-8").strip(), "[]")
            self.assertTrue((dest / "assets" / "nfc-public-colors.js").is_file())

    def test_remote_path_is_fixed(self):
        env = os.environ.copy()
        env["DEPLOY_PATH"] = "/var/www/other"
        proc = subprocess.run(
            ["bash", str(ROOT / "tools" / "deploy_public_colors.sh")],
            cwd=str(ROOT),
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("/var/www/shanghaidflab", proc.stderr)

    def test_readme_points_at_aliyun_only(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for token in (
            "/var/www/shanghaidflab",
            "106.15.198.252",
            "FEISHU_APP_ID",
            "FEISHU_APP_SECRET",
            "DEPLOY_SSH_USER",
            "data/colors.json",
            "沪ICP备2026039729号-1",
            "F-TEST01",
        ):
            self.assertIn(token, text)
        self.assertNotIn("185.199.108.153", text)
        self.assertNotIn("github.io", text.lower())

    def test_bridge_does_not_touch_gesture_assets(self):
        js = (ROOT / "assets" / "nfc-public-colors.js").read_text(encoding="utf-8")
        self.assertIn("data/colors.json", js)
        self.assertIn("libraryGrid", js)
        self.assertNotIn("nfc-scroll-assets", js)
        self.assertNotIn("swatches", js)


class HelperTests(unittest.TestCase):
    def test_image_magic(self):
        self.assertTrue(sync.looks_like_image(JPEG))
        self.assertTrue(sync.looks_like_image(b"\x89PNG\r\n\x1a\n"))
        self.assertFalse(sync.looks_like_image(b'{"ok":1}'))
        self.assertFalse(sync.looks_like_image(b"data:image/jpeg;base64,aaaa"))

    def test_no_network_constants_are_the_sample_base(self):
        self.assertEqual(sync.APP_TOKEN, "AvvUbYVazaJF1PsqNdgcQBgUn4b")
        self.assertEqual(sync.TABLE_ID, "tbl8AxaiNxueFhaT")
        self.assertNotIn("维禾", json.dumps({"app": sync.APP_TOKEN}))


if __name__ == "__main__":
    unittest.main()
