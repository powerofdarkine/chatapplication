#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#

"""
daemon.request
~~~~~~~~~~~~~~~~~

This module provides a Request object to manage and persist 
request settings (cookies, auth, proxies).
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from .dictionary import CaseInsensitiveDict
from .cookies import parse_cookie_header
from .http_consts import CRLF, CRLF2, NLINE2


class Request:
    """Server-side HTTP request container and parser.

    Summary:
        Parses an incoming raw HTTP/1.x request into method, path, version,
        headers, cookies, and body. Supports mapping to a route hook
        (function) via a provided routes table.

    Attributes:
        method (Optional[str]): HTTP method, e.g. "GET".
        url (Optional[str]): Unused for server parsing; kept for compatibility.
        path (Optional[str]): Request target path, e.g. "/index.html".
        version (Optional[str]): HTTP version string, e.g. "HTTP/1.1".
        headers (CaseInsensitiveDict): Parsed headers (case-insensitive keys).
        cookies (dict[str, str]): Parsed cookies from the Cookie header.
        body (str): Request body as text (raw bytes decoded as ISO-8859-1).
        routes (dict): Route table keyed by (METHOD, PATH) -> hook function.
        hook (Optional[callable]): Selected hook function, if any.

    Notes:
        - For server parsing, decoding request bytes as ISO-8859-1 is safe per
          RFC 7230 for header octets. Application code may re-decode body.
    """

    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "reason",
        "cookies",
        "routes",
        "hook",
        "path",
        "version",
    ]

    def __init__(self) -> None:
        """Initialize an empty Request."""
        self.method: Optional[str] = None
        self.url: Optional[str] = None
        self.path: Optional[str] = None
        self.version: Optional[str] = None

        # Case-insensitive header map for convenient lookups.
        self.headers: CaseInsensitiveDict = CaseInsensitiveDict()

        # Parsed cookie key/value pairs.
        self.cookies: Dict[str, str] = {}

        self.body: str = ""

        # Routing context
        self.routes: Dict = {}
        self.hook = None

    def extract_request_line(self, first_line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Parse the start-line: METHOD SP REQUEST-TARGET SP HTTP-VERSION.

        Inputs:
            - first_line (str): e.g., "GET /path HTTP/1.1"

        Outputs:
            - (method, path, version) or (None, None, None) on error.
        """
        try:
            first_line = first_line.strip(CRLF)
            parts = first_line.split()
            if len(parts) != 3:
                raise ValueError("Malformed request line")

            method, path, version = parts[0], parts[1], parts[2]

            if path == "/":
                path = "/index.html"

            return method, path, version
        except Exception as exc:
            print(f"[Request] Error parsing request line '{first_line}': {exc}")
            return None, None, None

    def prepare_headers(self, header_lines_list: Iterable[str]) -> CaseInsensitiveDict:
        """Parse header lines into a CaseInsensitiveDict.

        Inputs:
            - header_lines_list (Iterable[str]): raw header lines (without CRLFCRLF).

        Outputs:
            - CaseInsensitiveDict of headers.
        """
        headers = CaseInsensitiveDict()
        for raw in header_lines_list:
            line = raw.strip(CRLF)
            if not line:
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip()] = val.lstrip()
        return headers

    def prepare(self, request: str, routes: Optional[Dict] = None) -> None:
        """Parse a raw HTTP/1.x request into this Request instance.

        Args:
            request (str): raw request text. If the original was bytes,
              decode using ISO-8859-1 before calling this method.
            routes (dict|None): optional routing table keyed by (METHOD, PATH).

        Side-effects:
            Populates method/path/version/headers/cookies/body.
            If routes are provided, sets 'hook' to the matched function.
        """
        # 1) Split header block and body by the first blank line.
        header_block, body = self._split_headers_body(request)
        self.body = body

        # 2) Split request line and header lines.
        header_lines = header_block.splitlines()
        if not header_lines:
            print("[Request] Empty header block.")
            return

        first_line = header_lines[0]
        other_header_lines = header_lines[1:]

        # 3) Parse request line.
        self.method, self.path, self.version = self.extract_request_line(first_line)
        if not self.method or not self.path or not self.version:
            print("[Request] Could not parse request line. Aborting.")
            return

        print(f"[Request] {self.method} path {self.path} version {self.version}")

        # 4) Parse headers.
        self.headers = self.prepare_headers(other_header_lines)

        # 5) Parse cookies.
        cookie_string = self.headers.get('Cookie')
        if cookie_string:
            self.cookies = parse_cookie_header(cookie_string)

        # 6) Route hook (if routes provided).
        if routes:
            self.routes = routes
            self.hook = routes.get((self.method, self.path))

    def prepare_body(self, data, files, json=None):
        """Compatibility placeholder kept for API parity with client parsers.

        The server-side code does not implement the richer request body
        construction used by client libraries; this function exists only for
        compatibility and intentionally performs no work.
        """
        return

    def prepare_content_length(self, body):
        """Compatibility placeholder: content-length is handled elsewhere.

        The response builder is responsible for computing and setting the
        Content-Length header; this method is a no-op kept for compatibility.
        """
        return

    def prepare_auth(self, auth, url=""):
        """Compatibility placeholder: auth handled by higher-level logic."""
        return

    def prepare_cookies(self, cookies: str) -> None:
        """Set raw Cookie header value (server-side, rarely needed)."""
        self.headers["Cookie"] = cookies

    @staticmethod
    def _split_headers_body(raw: str) -> Tuple[str, str]:
        """Split raw request into (header_block, body) with tolerant line ending.

        Inputs:
            - raw (str): full request text.

        Outputs:
            - (header_block, body) where body may be "" if none present.
        """
        # Prefer CRLFCRLF separator, fall back to LF-only if needed.
        if CRLF2 in raw:
            parts = raw.split(CRLF2, 1)
            return parts[0], parts[1]
        
        # Fallback to LF-only double newline
        if NLINE2 in raw:
            parts = raw.split(NLINE2, 1)
            return parts[0], parts[1]

        return raw, ""
