"""Local HTTP server for the family-picker SPA and printable cover sheets."""

from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from leaflet.cover_page import build_family_cover_html
from leaflet.audit import DEFAULT_ROOT_INDI
from leaflet.gedcom import (
    GedcomData,
    family_on_lineage,
    family_picker_label,
    format_family_id,
    iter_families_for_picker,
    lineage_relatives,
    normalise_family_xref,
    parse_gedcom,
)

_SHEET_RE = re.compile(r"^/api/family/([^/]+)/sheet$")


class LeafletApp:
    """Shared state for the dev server."""

    def __init__(
        self,
        repo_root: Path,
        gedcom_path: Path,
        *,
        encoding: str = "utf-8",
        root_indi: str = DEFAULT_ROOT_INDI,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.gedcom_path = gedcom_path.resolve()
        self.encoding = encoding
        self.root_indi = root_indi
        self.data: GedcomData = parse_gedcom(self.gedcom_path, encoding=encoding)
        self._lineage = lineage_relatives(self.data, root_indi)

    def families_json(self) -> list[dict[str, str | bool]]:
        rows: list[dict[str, str | bool]] = []
        for fam in iter_families_for_picker(self.data):
            fid = format_family_id(fam.xref)
            rows.append(
                {
                    "id": fid,
                    "xref": fam.xref,
                    "label": family_picker_label(fam, self.data),
                    "lineage": family_on_lineage(fam, self.data, self._lineage),
                }
            )
        return rows

    def family_sheet_html(self, family_id: str) -> str | None:
        xref = normalise_family_xref(family_id)
        fam = self.data.families.get(xref)
        if fam is None:
            return None
        return build_family_cover_html(
            self.data,
            fam,
            repo_root=self.repo_root,
            assets_base="/",
            inline_css=True,
            root_indi=self.root_indi,
        )

    def resolve_static(self, url_path: str) -> Path | None:
        rel = url_path.lstrip("/")
        if not rel or ".." in rel.split("/"):
            return None
        target = (self.repo_root / rel).resolve()
        try:
            target.relative_to(self.repo_root)
        except ValueError:
            return None
        return target if target.is_file() else None


def _make_handler(app: LeafletApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LeafletHTTP/1.0"

        def log_message(self, fmt: str, *args) -> None:
            print(f"[leaflet] {self.address_string()} {fmt % args}")

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path in ("", "/"):
                self._send_file(app.repo_root / "assets/app/index.html")
                return

            if path == "/api/families":
                self._send_json({"families": app.families_json()})
                return

            m = _SHEET_RE.match(path)
            if m:
                html_doc = app.family_sheet_html(unquote(m.group(1)))
                if html_doc is None:
                    self._send_error(404, "Family not found")
                    return
                self._send_html(html_doc)
                return

            if path.startswith("/assets/"):
                target = app.resolve_static(path)
                if target is not None:
                    self._send_file(target)
                    return

            if path in ("/app.js", "/app.css"):
                target = app.repo_root / "assets/app" / path.lstrip("/")
                if target.is_file():
                    self._send_file(target)
                    return

            self._send_error(404, "Not found")

        def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path: Path) -> None:
            body = path.read_bytes()
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            self._send_bytes(200, body, ctype)

        def _send_html(self, html_doc: str) -> None:
            self._send_bytes(200, html_doc.encode("utf-8"), "text/html; charset=utf-8")

        def _send_json(self, payload: object) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send_bytes(200, body, "application/json; charset=utf-8")

        def _send_error(self, code: int, message: str) -> None:
            body = f"<p>{message}</p>".encode("utf-8")
            self._send_bytes(code, body, "text/html; charset=utf-8")

    return Handler


def run_server(
    gedcom_path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    repo_root: Path | None = None,
    encoding: str = "utf-8",
    root_indi: str = DEFAULT_ROOT_INDI,
) -> None:
    root = repo_root if repo_root is not None else Path(__file__).resolve().parent.parent
    app = LeafletApp(root, gedcom_path, encoding=encoding, root_indi=root_indi)
    handler = _make_handler(app)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"Leaflet: http://{host}:{port}/")
    print(f"GEDCOM: {gedcom_path}")
    print(f"Families: {len(app.data.families)}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
