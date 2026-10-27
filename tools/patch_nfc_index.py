#!/usr/bin/env python3
"""Insert the public-color bridge into the live NFC index, once.

Refuses to touch a page that is not the Aliyun NFC package: the file must
already contain the ICP footer, the brand line, and nfc-scroll-assets.
The gesture script is not rewritten. A second run is a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

SNIPPET = '<script src="assets/nfc-public-colors.js"></script>\n'
MARKER = "assets/nfc-public-colors.js"
REQUIRED = (
    "沪ICP备2026039729号-1",
    "上海·DF-LAB 色彩数据库",
    "nfc-scroll-assets",
)


def patch_html(html: str) -> str:
    missing = [token for token in REQUIRED if token not in html]
    if missing:
        raise ValueError(
            "refuse: this is not the NFC production index (missing %s)" % ", ".join(missing)
        )
    if "</body>" not in html:
        raise ValueError("refuse: NFC index has no </body>")
    if MARKER in html:
        return html
    return html.replace("</body>", SNIPPET + "</body>", 1)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: patch_nfc_index.py <index.html>", file=sys.stderr)
        return 2
    path = Path(args[0])
    original = path.read_text(encoding="utf-8")
    try:
        updated = patch_html(original)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print("patched %s" % path, file=sys.stderr)
    else:
        print("already patched %s" % path, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
