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
daemon.response
~~~~~~~~~~~~~~~~~

This module provides a :class: `Response <Response>` object to manage and persist 
response settings (cookies, auth, proxies), and to construct HTTP responses
based on incoming requests. 

The current version supports MIME type detection, content loading and header formatting
"""

import datetime
import mimetypes
import os
from typing import Optional, Union, Dict

from .dictionary import CaseInsensitiveDict
from .cookies import make_set_cookie, Cookie
from .http_consts import (
    CRLF,
    CRLF2,
    HTTP_1_1,
    HEADER_SET_COOKIE,
    HEADER_CONTENT_LENGTH,
    HEADER_CONNECTION,
    CONNECTION_CLOSE,
    HEADER_CONTENT_TYPE,
    HEADER_LOCATION,
    DATE_FORMAT,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Response:
    """Container for an HTTP response.

    Summary:
        Holds status, headers, cookies, and body bytes. Provides helpers to
        populate dynamic content (from route hooks), resolve MIME types and
        load static files, and render a complete HTTP/1.1 response.

    Attributes:
        status_code (Optional[int]): HTTP status code (e.g., 200, 404).
        reason (Optional[str]): Reason phrase (e.g., "OK").
        headers (dict[str, str]): Header map (case preserved).
        cookies (CaseInsensitiveDict): Cookie name -> raw cookie string.
        _content (bytes|bool): Response body bytes, or False if unset.
        _has_dynamic_content (bool): Whether a hook has provided content.
        request: Optional originating request reference (not required).
    """

    __attrs__ = [
        "_content",
        "_header",
        "status_code",
        "method",
        "headers",
        "url",
        "history",
        "encoding",
        "reason",
        "cookies",
        "elapsed",
        "request",
        "body",
    ]

    def __init__(self, request=None) -> None:
        """Initialize a new empty Response.

        Inputs:
            - request (optional): request object reference for adapters.

        Outputs:
            - Response instance with default fields.
        """
        self.request = request
        self.status_code: Optional[int] = None
        self.reason: Optional[str] = None
        self.headers = CaseInsensitiveDict()
        self.cookies: Dict[str, Cookie] = {}

        self._content: Union[bytes, bool] = False
        self._has_dynamic_content = False

    def set_dynamic_content(self, hook_data: Optional[dict]) -> None:
        """Populate response from a route hook.

        Inputs:
            - hook_data (dict|None): may contain:
                * status (int)
                * headers (dict[str,str])
                * cookies (dict[name, raw_value])
                * body (str|bytes|any)

        Side-effects:
            - Updates status_code/reason/headers/cookies/_content.
            - Marks response as having dynamic content.
        """
        if not hook_data:
            return
        
        self._has_dynamic_content = True
        self.status_code = hook_data.get("status", self.status_code or 200)

        for k, v in (hook_data.get("headers") or {}).items():
            self.headers[k] = v

        # Accept both 'cookies' and legacy 'Cookies' keys
        for name, val in (hook_data.get("cookies") or hook_data.get("Cookies") or {}).items():
            if isinstance(val, Cookie):
                self.cookies[name] = val
            elif isinstance(val, dict):
                self.cookies[name] = Cookie(
                    name,
                    val.get('value', ''),
                    val.get('path', '/'),
                    val.get('max_age'),
                    val.get('httponly', True),
                    val.get('secure', False),
                )
            else:
                self.cookies[name] = Cookie(name, str(val))
        
        body = hook_data.get("body")

        if isinstance(body, bytes):
            self._content = body
        elif isinstance(body, str):
            self._content = body.encode("utf-8")
        elif body is None:
            pass

    def set_error(self, code: int, reason: str) -> None:
        """
        Set an error response, (sets status, reason, content, and Content-Type header).

        :param code: HTTP status code (e.g., 500).
        :param reason: Reason phrase (e.g., "Internal Server Error").
        """
        self.status_code = code
        self.reason = reason
        self._content = f"{code} {reason}".encode("utf-8")
        self.headers[HEADER_CONTENT_TYPE] = "text/plain; charset=utf-8"

    def get_mime_type(self, path: str) -> str:
        """
        Guess MIME type from path. e.g., "text/css", default "application/octet-stream"

        :param path (str): request path (e.g., "/css/chat.css").
        """
        if not mimetypes.inited:
            mimetypes.init()
        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return "application/octet-stream"
        return mime_type or "application/octet-stream"

    def prepare_content_type(self, mime_type: str = "text/html") -> str:
        """
        Set Content-Type and choose the base directory for static resolution. Sets self.headers['Content-Type'] to the provided mime_type.
        Args:
            mime_type (str): resolved MIME type.
        
        Returns:
            str: filesystem base directory for the given MIME.
        """
        base_dir = ""

        try:
            main_type, sub_type = mime_type.split("/", 1)
        except ValueError:
            main_type = "application"
            sub_type = "octet-stream"

        self.headers[HEADER_CONTENT_TYPE] = mime_type

        if main_type == "text":
            if sub_type == "html":
                base_dir = os.path.join(BASE_DIR, "www")
            elif sub_type == "css":
                base_dir = os.path.join(BASE_DIR, "static", "css")
            elif sub_type == "javascript":
                base_dir = os.path.join(BASE_DIR, "static", "js")
            else:
                base_dir = os.path.join(BASE_DIR, "static")
        elif main_type == "image":
            base_dir = os.path.join(BASE_DIR, "static", "images")
        elif main_type == "application":
            if sub_type == "javascript":
                base_dir = os.path.join(BASE_DIR, "static", "js")
            else:
                base_dir = os.path.join(BASE_DIR, "apps")
        else:
            base_dir = os.path.join(BASE_DIR, "static")

        return base_dir

    def build_content(self, path: str, base_dir: str) -> tuple[int, bytes]:
        """Load a static object under base_dir.

        Inputs:
            - path (str): request path (e.g., "/css/chat.css").
            - base_dir (str): base directory chosen by prepare_content_type().

        Outputs:
            - (length, content) where content is file bytes.

        Raises:
            - FileNotFoundError: if the file does not exist or invalid path.
        """
        # Strip query string (e.g., "/?fbclid=..." -> "/")
        path_without_query = path.split('?')[0] if '?' in path else path
        rel = os.path.normpath(path_without_query.lstrip("/"))
        base_leaf = os.path.basename(os.path.normpath(base_dir))

        # Collapse leading duplicates, e.g., "css/css/file.css"
        while rel.startswith(base_leaf + os.sep) or rel == base_leaf:
            if rel == base_leaf:
                rel = ""
                break
            rel = rel[len(base_leaf) + 1 :]

        filepath = os.path.normpath(os.path.join(base_dir, rel)) if rel else os.path.normpath(base_dir)

        print(f"[Response] Serving static path: {filepath}")

        try:
            if os.path.isdir(filepath):
                index_path = os.path.join(filepath, "index.html")
                if os.path.exists(index_path):
                    filepath = index_path
                else:
                    print(f"[Response] Directory without index: {filepath}")
                    raise FileNotFoundError

            with open(filepath, "rb") as f:
                content = f.read()
            return len(content), content

        except FileNotFoundError:
            print(f"[Response] File not found: {filepath}")
            raise
        except IsADirectoryError:
            print(f"[Response] Attempted to read a directory: {filepath}")
            raise FileNotFoundError

    def build_response_bytes(self) -> bytes:
        status = self.status_code or 200
        reason = self.reason or _reason_phrase_for(status)
        body_bytes = self._content or b""

        # Ensure essential headers
        if HEADER_CONTENT_LENGTH not in self.headers:
            self.headers[HEADER_CONTENT_LENGTH] = str(len(body_bytes))
        if HEADER_CONNECTION not in self.headers:
            self.headers[HEADER_CONNECTION] = CONNECTION_CLOSE

        header_lines = [f"{HTTP_1_1} {status} {reason}"]

        for k, v in self.headers.items():
            header_lines.append(f"{k}: {v}")
        for name, cookie_obj in self.cookies.items():
            if isinstance(cookie_obj, Cookie):
                rendered = cookie_obj.render_set_cookie()
            elif isinstance(cookie_obj, dict):
                # Coerce dict to Cookie dataclass with logging
                print(f"[Response] Coercing cookie dict for '{name}' to Cookie")
                cookie_obj = Cookie(
                    name,
                    cookie_obj.get("value", ""),
                    cookie_obj.get("path", "/"),
                    cookie_obj.get("max_age"),
                    cookie_obj.get("httponly", True),
                    cookie_obj.get("secure", False),
                )
                rendered = cookie_obj.render_set_cookie()
            else:
                rendered = make_set_cookie(name, str(cookie_obj))

            header_lines.append(f"{HEADER_SET_COOKIE}: {rendered}")

        header_block = CRLF.join(header_lines) + CRLF2
        return header_block.encode("utf-8") + (body_bytes or b"")

    @classmethod
    def simple(cls, status: int, reason: str, body_text: str = "", content_type: str = "text/plain; charset=utf-8"):
        r = cls()
        r.status_code = status
        r.reason = reason
        r.headers[HEADER_CONTENT_TYPE] = content_type
        r._content = body_text.encode("utf-8")
        return r

    @classmethod
    def bad_request(cls, body_text: str = "400 Bad Request"):
        return cls.simple(400, "Bad Request", body_text)
    
    @classmethod
    def not_found(cls, body_text: str = "404 Not Found"):
        return cls.simple(404, "Not Found", body_text)
    
    @classmethod
    def bad_gateway(cls, body_text: str = "502 Bad Gateway"):
        return cls.simple(502, "Bad Gateway", body_text)
    
    @classmethod
    def redirect(cls, location: str, body_text: str = "<html><body>Redirect</body></html>"):
        r = cls.simple(302, "Found", body_text, content_type="text/html; charset=utf-8")
        r.headers[HEADER_LOCATION] = location
        return r

    def build_response_header(self, request=None) -> bytes:
        """Render HTTP/1.1 header block for current state.

        Outputs:
            - header bytes suitable to be written to a socket.
        """
        full = self.build_response_bytes()
        marker = CRLF2.encode("utf-8")
        idx = full.find(marker)
        if idx == -1:
            return full
        return full[: idx + len(marker)]

    def build_notfound(self) -> bytes:
        """Return a minimal 404 response (header + body)."""
        self.status_code = 404
        self.reason = "Not Found"
        self.headers[HEADER_CONTENT_TYPE] = "text/html; charset=utf-8"
        self._content = b"<html><body><h1>404 Not Found</h1></body></html>"
        return self.build_response_bytes()

    def build_static_filepath(self, request_path: str) -> str:
        """Map a static request path into the static directory.

        Inputs:
            - request_path (str): e.g., "/css/chat.css" or "js/chat.js"

        Outputs:
            - absolute path within BASE_DIR/static/...

        Raises:
            - FileNotFoundError on traversal attempts.
        """
        rel = os.path.normpath(request_path.lstrip("/"))
        if rel.startswith(".."):
            raise FileNotFoundError("Invalid path")
        return os.path.join(BASE_DIR, "static", rel)

    def build_response(self, request=None) -> bytes:
        """Build a complete HTTP response.

        Flow:
            1) If dynamic content (or error) was set by a hook → return it.
            2) Else if an error status is already set → return it.
            3) Else attempt to serve static content resolved by request.path.
            4) Fallback to empty 200.

        Outputs:
            - header + body bytes.
        """
        # 1) Dynamic content path
        if self._has_dynamic_content:
            header = self.build_response_header(request)
            return header + (self._content or b"")

        # 2) Explicit error path
        if self.status_code and self.status_code >= 400:
            header = self.build_response_header(request)
            return header + (self._content or b"")

        # 3) Static content path
        if request and getattr(request, "path", None):
            try:
                mime_type = self.get_mime_type(request.path)
                base_dir = self.prepare_content_type(mime_type)
                _, content = self.build_content(request.path, base_dir)
                self._content = content

                if HEADER_CONTENT_TYPE not in self.headers:
                    self.headers[HEADER_CONTENT_TYPE] = mime_type

                if not self.status_code:
                    self.status_code = 200
                    self.reason = "OK"

                return self.build_response_bytes()

            except (FileNotFoundError, IsADirectoryError):
                return self.build_notfound()
            except Exception as exc:
                print(f"[Response] Error building response: {exc}")
                import traceback

                traceback.print_exc()
                self.set_error(500, "Internal Server Error")
                return self.build_response_bytes()

        # 4) Fallback: empty 200
        if not self._content:
            self._content = b""
        if not self.status_code:
            self.status_code = 200
            self.reason = "OK"

        return self.build_response_bytes()

    def set_cookie(
        self,
        name: str,
        value: str,
        max_age: Optional[int] = None,
        path: str = "/",
        httponly: bool = True,
        secure: bool = False,
    ) -> None:
        """Set a cookie on the response.

        Args:
            name (str): cookie name.
            value (str): cookie value (unquoted).
            max_age (int|None): optional Max-Age attribute in seconds.
            path (str): Path attribute (default '/').
            httponly (bool): add HttpOnly attribute.
            secure (bool): add Secure attribute.

        Side-effects:
            Adds/overwrites a raw cookie string into self.cookies.
        """
        self.cookies[name] = Cookie(name, value, path, max_age, httponly, secure)

def _reason_phrase_for(code: int) -> str:
    """Return the standard reason phrase for a given HTTP status code.

    Args:
        code (int): HTTP status code.

    Returns:
        str: Reason phrase for the status code (default "OK" if unknown).
    """
    return {
        200: "OK",
        302: "Found",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        500: "Internal Server Error",
        502: "Bad Gateway",
    }.get(code, "OK")