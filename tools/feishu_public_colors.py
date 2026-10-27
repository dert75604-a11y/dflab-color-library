#!/usr/bin/env python3
"""Pull DF-LAB colors marked 公开上架 in Feishu and write the public site files.

Outputs (under the repo root, or --out-dir):

- data/colors.json          array of public cards, no 备注 and no base64
- assets/colors/<code>.<ext>
- assets/colors/<code>-macro.<ext>   only when 特写 exists
- data/sync-report.json     skip reasons, never the 备注 text

The live site is the NFC package on 106.15.198.252. This tool does not upload
that package and does not talk to GitHub Pages. Deploy with
tools/deploy_public_colors.sh, which copies only data/colors.json,
assets/colors/, and assets/nfc-public-colors.js.

Without FEISHU_APP_ID/FEISHU_APP_SECRET or an access token, use --fixture or
--dry-run --fixture. Live Feishu calls are not attempted in that mode.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

APP_TOKEN = "AvvUbYVazaJF1PsqNdgcQBgUn4b"
TABLE_ID = "tbl8AxaiNxueFhaT"
VIEW_ID = "vewggbVU5M"
OPEN_API = "https://open.feishu.cn"

CODE_RE = re.compile(r"^F-\d{5}$")
ASSET_NAME_RE = re.compile(r"^F-\d{5}(-macro)?\.(jpg|png|webp)$")
DEFAULT_STATUS_ALLOW = ("终板通过", "已上架")
PUBLIC_KEYS = (
    "code",
    "name",
    "color",
    "finish",
    "species",
    "image",
    "imageCloseup",
    "uploader",
    "tags",
)
# Never copy these onto the public site, even if a future field is added.
FORBIDDEN_KEYS = {
    "备注",
    "配方",
    "克数",
    "formula",
    "recipe",
    "grams",
    "note",
    "notes",
    "remark",
    "remarks",
}
IMAGE_MAGIC = (
    b"\xff\xd8",
    b"\x89PNG",
    b"RIFF",
)


def as_text(value):
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value).strip()
    if isinstance(value, dict):
        return as_text(value.get("text") or value.get("name") or value.get("value"))
    if isinstance(value, list):
        parts = [as_text(item) for item in value]
        # Rich text is a list of {text} segments and should stay one string.
        if value and all(isinstance(item, dict) and "text" in item for item in value):
            return "".join(parts).strip()
        return " ".join(part for part in parts if part).strip()
    return str(value).strip()


def as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "是"}
    if isinstance(value, list) and value:
        return as_bool(value[0])
    if isinstance(value, dict):
        return as_bool(value.get("value") if "value" in value else value.get("text"))
    return False


def as_attachments(value):
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    found = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if item.get("file_token") or item.get("url") or item.get("tmp_url") or item.get("local_path"):
            found.append(item)
    return found


def fields_of(record):
    if not isinstance(record, dict):
        return {}
    fields = record.get("fields")
    if isinstance(fields, dict):
        return fields
    return record


def record_id_of(record):
    if isinstance(record, dict):
        return as_text(record.get("record_id") or record.get("id"))
    return ""


def normalize_hex(value):
    text = as_text(value).strip()
    if not text:
        return ""
    if not text.startswith("#"):
        text = "#" + text
    match = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", text)
    if not match:
        return ""
    hex_digits = match.group(1).upper()
    if len(hex_digits) == 3:
        hex_digits = "".join(ch * 2 for ch in hex_digits)
    return "#" + hex_digits


def status_allowlist(raw=None):
    if raw is None:
        raw = os.environ.get("FEISHU_STATUS_ALLOW", "")
    if not raw:
        return set(DEFAULT_STATUS_ALLOW)
    return {part.strip() for part in raw.split(",") if part.strip()}


def classify(record, allowed_status):
    """Return (reason, None) to skip, or (None, prepared) to publish.

    Unchecked rows lose before any other check, so F-TEST01 stays out while
    公开上架 is false even if every other column is filled.
    """
    fields = fields_of(record)
    if not as_bool(fields.get("公开上架")):
        return "not_public", None
    code = as_text(fields.get("code")).upper()
    if not CODE_RE.fullmatch(code):
        return "code_format", None
    name = as_text(fields.get("name"))
    if not name:
        return "name", None
    finish = as_text(fields.get("finish"))
    if not finish:
        return "finish", None
    status = as_text(fields.get("状态") or fields.get("status"))
    if status not in allowed_status:
        return "status", None
    images = as_attachments(fields.get("主图") or fields.get("image"))
    if not images:
        return "image", None
    closeups = as_attachments(fields.get("特写") or fields.get("imageCloseup"))
    species = as_text(fields.get("树种") or fields.get("species"))
    tags = []
    for part in (species, finish):
        if part and part not in tags:
            tags.append(part)
    prepared = {
        "record_id": record_id_of(record),
        "code": code,
        "name": name,
        "finish": finish,
        "species": species,
        "color": normalize_hex(fields.get("hex") or fields.get("color")),
        "uploader": as_text(fields.get("uploader")) or "DF-LAB",
        "tags": tags,
        "status": status,
        "main": images[0],
        "closeup": closeups[0] if closeups else None,
    }
    return None, prepared


def public_item(prepared, image_url, closeup_url=""):
    # Key order matches the public card contract. Optional keys are omitted
    # when the source row has no hex or no close-up, never filled with guesses.
    item = {
        "code": prepared["code"],
        "name": prepared["name"],
    }
    if prepared.get("color"):
        item["color"] = prepared["color"]
    item["finish"] = prepared["finish"]
    if prepared.get("species"):
        item["species"] = prepared["species"]
    item["image"] = image_url
    if closeup_url:
        item["imageCloseup"] = closeup_url
    item["uploader"] = prepared["uploader"] or "DF-LAB"
    item["tags"] = list(prepared["tags"])
    leaked = FORBIDDEN_KEYS.intersection(item)
    if leaked:
        raise RuntimeError("refusing to publish forbidden keys: %s" % sorted(leaked))
    unknown = set(item) - set(PUBLIC_KEYS)
    if unknown:
        raise RuntimeError("refusing to publish unknown keys: %s" % sorted(unknown))
    blob = json.dumps(item, ensure_ascii=False)
    if "data:image" in blob or "base64," in blob:
        raise RuntimeError("refusing to publish embedded image data for %s" % item["code"])
    return item


def safe_ext(name):
    ext = Path(as_text(name)).suffix.lower()
    if ext == ".jpeg":
        return ".jpg"
    if ext in {".jpg", ".png", ".webp"}:
        return ext
    return ".jpg"


def asset_paths(code, main_name, closeup_name=None):
    main = "/assets/colors/%s%s" % (code, safe_ext(main_name))
    close = ""
    if closeup_name is not None:
        close = "/assets/colors/%s-macro%s" % (code, safe_ext(closeup_name))
    return main, close


def looks_like_image(blob):
    if not blob or blob.startswith((b"{", b"[", b"<", b"data:")):
        return False
    if blob.startswith(b"RIFF"):
        return b"WEBP" in blob[:16]
    return blob.startswith(IMAGE_MAGIC[:2])


def _request(url, token=None, method="GET", payload=None, timeout=60):
    data = None
    headers = {"User-Agent": "dflab-public-colors/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError("Feishu HTTP %s: %s" % (exc.code, detail)) from exc
    return body, content_type


def tenant_token(app_id, app_secret, base_url=OPEN_API):
    body, _ = _request(
        base_url.rstrip("/") + "/open-apis/auth/v3/tenant_access_token/internal",
        method="POST",
        payload={"app_id": app_id, "app_secret": app_secret},
    )
    parsed = json.loads(body.decode("utf-8"))
    if parsed.get("code") not in (0, None) or not parsed.get("tenant_access_token"):
        raise RuntimeError("Feishu token error: %s" % parsed.get("msg", parsed.get("code")))
    return parsed["tenant_access_token"]


def resolve_token(base_url=OPEN_API):
    existing = os.environ.get("FEISHU_TENANT_ACCESS_TOKEN") or os.environ.get("FEISHU_USER_ACCESS_TOKEN")
    if existing:
        return existing.strip()
    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise RuntimeError(
            "Missing Feishu credentials. Set FEISHU_APP_ID and FEISHU_APP_SECRET, "
            "or FEISHU_TENANT_ACCESS_TOKEN / FEISHU_USER_ACCESS_TOKEN. "
            "Or pass --fixture for a local dry run."
        )
    return tenant_token(app_id, app_secret, base_url=base_url)


def list_records(token, app_token, table_id, view_id, base_url=OPEN_API):
    url = "%s/open-apis/bitable/v1/apps/%s/tables/%s/records/search" % (
        base_url.rstrip("/"),
        urllib.parse.quote(app_token),
        urllib.parse.quote(table_id),
    )
    items = []
    page_token = ""
    for _ in range(50):
        payload = {
            "view_id": view_id,
            "automatic_fields": False,
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {"field_name": "公开上架", "operator": "is", "value": ["true"]},
                ],
            },
        }
        query = "?page_size=500"
        if page_token:
            query += "&page_token=" + urllib.parse.quote(page_token)
        body, _ = _request(url + query, token=token, method="POST", payload=payload)
        parsed = json.loads(body.decode("utf-8"))
        if parsed.get("code") not in (0, None):
            raise RuntimeError("Feishu record search failed: %s" % parsed.get("msg", parsed))
        data = parsed.get("data") or {}
        items.extend(data.get("items") or [])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token") or ""
        if not page_token:
            break
    return items


def download_attachment(token, attachment, table_id, base_url=OPEN_API, allow_local=False, local_base=None):
    if allow_local and attachment.get("local_path"):
        path = Path(attachment["local_path"])
        if not path.is_absolute():
            path = (local_base or Path.cwd()) / path
        blob = path.resolve().read_bytes()
        if not looks_like_image(blob):
            raise RuntimeError("local file is not an image: %s" % path.name)
        return blob
    file_token = as_text(attachment.get("file_token"))
    extra = urllib.parse.quote(json.dumps({"bitablePerm": {"tableId": table_id}}, ensure_ascii=False))
    candidates = []
    for key in ("tmp_url", "url"):
        raw = as_text(attachment.get(key))
        if raw.startswith("https://"):
            candidates.append(raw)
    if file_token:
        candidates.append(
            "%s/open-apis/drive/v1/medias/%s/download?extra=%s"
            % (base_url.rstrip("/"), urllib.parse.quote(file_token), extra)
        )
    if not candidates:
        raise RuntimeError("attachment has no file_token or url")
    last_error = "no image bytes"
    for url in candidates:
        try:
            blob, content_type = _request(url, token=token)
        except RuntimeError as exc:
            last_error = str(exc)
            continue
        if "json" in content_type.lower() or not looks_like_image(blob):
            last_error = "response was not an image (%s, %s bytes)" % (content_type, len(blob))
            continue
        return blob
    raise RuntimeError(last_error)


def load_fixture(path):
    parsed = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("records"), list):
        return parsed["records"]
    raise RuntimeError("fixture must be a list or {\"records\": [...]}")


def _write_bytes(path: Path, blob: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(blob)
    tmp.replace(path)


def build_catalog(records, dest_root, fetch_image, allowed_status):
    """Classify records and store image files. Full rebuild: callers prune afterwards."""
    dest_root = Path(dest_root)
    image_dir = dest_root / "assets" / "colors"
    image_dir.mkdir(parents=True, exist_ok=True)
    skipped = []
    catalog = []
    kept_names = set()
    seen_codes = set()
    writebacks = []
    for record in records:
        reason, prepared = classify(record, allowed_status)
        label = ""
        if prepared:
            label = prepared["code"]
        else:
            label = as_text(fields_of(record).get("code")) or record_id_of(record) or "?"
        if reason:
            skipped.append({"code": label, "reason": reason})
            continue
        if prepared["code"] in seen_codes:
            skipped.append({"code": prepared["code"], "reason": "duplicate"})
            continue
        main_ext = safe_ext(prepared["main"].get("name"))
        main_file = image_dir / ("%s%s" % (prepared["code"], main_ext))
        close_file = None
        try:
            main_blob = fetch_image(prepared["main"])
            if not looks_like_image(main_blob):
                raise RuntimeError("main image is not a jpeg, png, or webp")
            _write_bytes(main_file, main_blob)
            if prepared["closeup"]:
                close_ext = safe_ext(prepared["closeup"].get("name"))
                close_file = image_dir / ("%s-macro%s" % (prepared["code"], close_ext))
                close_blob = fetch_image(prepared["closeup"])
                if not looks_like_image(close_blob):
                    raise RuntimeError("close-up is not a jpeg, png, or webp")
                _write_bytes(close_file, close_blob)
        except Exception as exc:  # noqa: BLE001 - one bad file must not publish the row
            for path in (main_file, close_file):
                if path and path.exists():
                    path.unlink()
            skipped.append({"code": prepared["code"], "reason": "image_download", "detail": str(exc)})
            continue
        image_url, close_url = asset_paths(
            prepared["code"],
            main_file.name,
            close_file.name if close_file else None,
        )
        catalog.append(public_item(prepared, image_url, close_url))
        seen_codes.add(prepared["code"])
        kept_names.add(main_file.name)
        if close_file:
            kept_names.add(close_file.name)
        if prepared["status"] != "已上架" and prepared["record_id"]:
            writebacks.append(prepared["record_id"])
    catalog.sort(key=lambda item: item["code"])
    return catalog, skipped, kept_names, writebacks


def prune_images(image_dir: Path, kept_names):
    if not image_dir.exists():
        return []
    removed = []
    for path in image_dir.iterdir():
        if not path.is_file():
            continue
        if path.name == ".gitkeep":
            continue
        if ASSET_NAME_RE.fullmatch(path.name) and path.name not in kept_names:
            path.unlink()
            removed.append(path.name)
    return removed


def write_outputs(dest_root: Path, catalog, skipped, removed):
    data_dir = dest_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    colors_path = data_dir / "colors.json"
    payload = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    if "备注" in payload or "data:image" in payload or "base64," in payload:
        raise RuntimeError("public JSON failed the no-notes / no-base64 check")
    tmp = colors_path.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(colors_path)
    report = {
        "published": [item["code"] for item in catalog],
        "skipped": skipped,
        "removed_images": removed,
    }
    report_path = data_dir / "sync-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return colors_path, report


def writeback_status(token, app_token, table_id, record_ids, base_url=OPEN_API):
    updated = []
    for record_id in record_ids:
        url = "%s/open-apis/bitable/v1/apps/%s/tables/%s/records/%s" % (
            base_url.rstrip("/"),
            urllib.parse.quote(app_token),
            urllib.parse.quote(table_id),
            urllib.parse.quote(record_id),
        )
        body, _ = _request(
            url,
            token=token,
            method="PUT",
            payload={"fields": {"状态": "已上架"}},
        )
        parsed = json.loads(body.decode("utf-8"))
        if parsed.get("code") not in (0, None):
            raise RuntimeError("writeback failed for %s: %s" % (record_id, parsed.get("msg")))
        updated.append(record_id)
    return updated


def make_fetcher(token, table_id, allow_local, local_base, base_url):
    def fetch(attachment):
        return download_attachment(
            token,
            attachment,
            table_id,
            base_url=base_url,
            allow_local=allow_local,
            local_base=local_base,
        )

    return fetch


def sync(records, dest_root, fetch_image, allowed_status):
    catalog, skipped, kept_names, writebacks = build_catalog(
        records, dest_root, fetch_image, allowed_status
    )
    removed = prune_images(Path(dest_root) / "assets" / "colors", kept_names)
    colors_path, report = write_outputs(Path(dest_root), catalog, skipped, removed)
    report["writeback_record_ids"] = writebacks
    return colors_path, report


def dry_run(records, allowed_status):
    """Classify without downloading or writing. Image URLs are the paths a real sync would use."""
    catalog = []
    skipped = []
    seen = set()
    for record in records:
        reason, prepared = classify(record, allowed_status)
        label = as_text(fields_of(record).get("code")) or "?"
        if reason:
            skipped.append({"code": label, "reason": reason})
            continue
        if prepared["code"] in seen:
            skipped.append({"code": prepared["code"], "reason": "duplicate"})
            continue
        seen.add(prepared["code"])
        image_url, close_url = asset_paths(
            prepared["code"],
            prepared["main"].get("name") or "main.jpg",
            (prepared["closeup"].get("name") or "macro.jpg") if prepared["closeup"] else None,
        )
        catalog.append(public_item(prepared, image_url, close_url))
    catalog.sort(key=lambda item: item["code"])
    return catalog, skipped


def repo_root():
    return Path(__file__).resolve().parents[1]


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Export Feishu 公开上架 colors to data/colors.json")
    parser.add_argument("command", nargs="?", default="sync", choices=("sync",))
    parser.add_argument("--fixture", help="Local records JSON. Skips Feishu auth.")
    parser.add_argument("--dry-run", action="store_true", help="Print the public JSON, write nothing.")
    parser.add_argument("--out-dir", default="", help="Output root. Default: repository root.")
    parser.add_argument(
        "--writeback-status",
        action="store_true",
        help="After a successful live publish, set 状态 to 已上架. Off by default.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    allowed = status_allowlist()
    base_url = os.environ.get("FEISHU_BASE_URL", OPEN_API).strip() or OPEN_API
    app_token = os.environ.get("FEISHU_APP_TOKEN", APP_TOKEN).strip() or APP_TOKEN
    table_id = os.environ.get("FEISHU_TABLE_ID", TABLE_ID).strip() or TABLE_ID
    view_id = os.environ.get("FEISHU_VIEW_ID", VIEW_ID).strip() or VIEW_ID
    out_dir = Path(args.out_dir).resolve() if args.out_dir else repo_root()

    if args.fixture:
        records = load_fixture(args.fixture)
        token = ""
    else:
        try:
            token = resolve_token(base_url=base_url)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        try:
            records = list_records(token, app_token, table_id, view_id, base_url=base_url)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if args.dry_run:
        catalog, skipped = dry_run(records, allowed)
        json.dump(catalog, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        print(
            "dry-run published=%s skipped=%s (nothing written)"
            % (len(catalog), len(skipped)),
            file=sys.stderr,
        )
        return 0

    local_base = Path(args.fixture).resolve().parent if args.fixture else repo_root()
    if args.fixture:
        # Fixture paths are relative to the current working directory when they
        # point at tests/fixtures/..., and also relative to the fixture file.
        def fetch(attachment, _base=local_base):
            if attachment.get("local_path"):
                try:
                    return download_attachment(
                        "",
                        attachment,
                        table_id,
                        allow_local=True,
                        local_base=Path.cwd(),
                    )
                except (OSError, RuntimeError):
                    return download_attachment(
                        "",
                        attachment,
                        table_id,
                        allow_local=True,
                        local_base=_base,
                    )
            raise RuntimeError("fixture attachment needs local_path")
    else:
        fetch = make_fetcher(token, table_id, allow_local=False, local_base=None, base_url=base_url)

    try:
        _colors_path, report = sync(records, out_dir, fetch, allowed)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.writeback_status and not args.fixture:
        try:
            writeback_status(
                token,
                app_token,
                table_id,
                report.get("writeback_record_ids") or [],
                base_url=base_url,
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    elif args.writeback_status and args.fixture:
        print("writeback skipped in fixture mode", file=sys.stderr)

    print(
        "published=%s skipped=%s -> %s"
        % (len(report["published"]), len(report["skipped"]), out_dir / "data" / "colors.json"),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
