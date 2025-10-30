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
import os
import mimetypes
import json # <--- HOÀN THIỆN: Thêm thư viện json
from .dictionary import CaseInsensitiveDict

# <--- HOÀN THIỆN: Đặt BASE_DIR trỏ đến thư mục gốc của dự án
# (Giả sử file này nằm trong daemon/, thì '..' là thư mục chứa daemon/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Response():
    """The :class:`Response <Response>` object, which contains a
    server's response to an HTTP request.
    ...
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
        "reason",
    ]


    def __init__(self, request=None):
        """
        Initializes a new :class:`Response <Response>` object.

        : params request : The originating request object.
        """

        self._content = False # Sẽ là bytes nếu có nội dung
        self._content_consumed = False
        self._next = None
        self._has_dynamic_content = False

        self.status_code = None
        self.headers = {} # Sử dụng dict thay vì CaseInsensitiveDict
        self.url = None
        self.encoding = None
        self.history = []
        self.reason = None
        self.cookies = CaseInsensitiveDict()
        self.elapsed = datetime.timedelta(0)
        self.request = None

    # <--- HOÀN THIỆN: Thêm hàm này để HttpAdapter gọi
    def set_dynamic_content(self, hook_data):
        """
        Set response từ hook (WeApRous route handler).
        
        :param hook_data: dict với keys: status, headers, cookies, body
        """
        if not hook_data:
            return
        
        # Set status code
        if 'status' in hook_data:
            self.status_code = hook_data['status']
            # Map status code to reason phrase
            status_map = {
                200: 'OK', 201: 'Created', 204: 'No Content',
                301: 'Moved Permanently', 302: 'Found', 304: 'Not Modified',
                400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found',
                500: 'Internal Server Error', 502: 'Bad Gateway', 503: 'Service Unavailable'
            }
            self.reason = status_map.get(self.status_code, 'Unknown')
        
        # Set headers
        if 'headers' in hook_data:
            for key, value in hook_data['headers'].items():
                self.headers[key] = value
        
        # Set cookies từ hook
        if 'cookies' in hook_data:
            for name, value in hook_data['cookies'].items():
                # Cookie value từ hook đã có format đầy đủ (e.g., "value; Path=/; HttpOnly")
                self.cookies[name] = value
        
        # Set body
        if 'body' in hook_data:
            body = hook_data['body']
            if isinstance(body, str):
                self._content = body.encode('utf-8')
            elif isinstance(body, bytes):
                self._content = body
            else:
                self._content = str(body).encode('utf-8')
        else:
            # Nếu không có body (ví dụ: 302 redirect), set empty content
            self._content = b''
        
        self._has_dynamic_content = True
    
    # <--- HOÀN THIỆN: Thêm hàm này để HttpAdapter gọi
    def set_error(self, code, reason):
        """
        Sets an error status (e.g., 500) if a hook fails.
        """
        self.status_code = code
        self.reason = reason
        self._content = f"{code} {reason}".encode('utf-8')
        self.headers['Content-Type'] = 'text/plain'
        self._has_dynamic_content = True
    # --- KẾT THÚC HOÀN THIỆN

    def get_mime_type(self, path):
        """
        Determines the MIME type of a file based on its path.
        ...
        """
        # <--- CẢI TIẾN: Thêm thư viện mimetypes nếu chưa có
        if not mimetypes.inited:
            mimetypes.init()
        # --- KẾT THÚC CẢI TIẾN
            
        try:
            mime_type, _ = mimetypes.guess_type(path)
        except Exception:
            return 'application/octet-stream'
        return mime_type or 'application/octet-stream'


    def prepare_content_type(self, mime_type='text/html'):
        """
        Prepares the Content-Type header and determines the base directory
        ...
        """
        
        base_dir = ""

        # Processing mime_type based on main_type and sub_type
        try:
            main_type, sub_type = mime_type.split('/', 1)
        except ValueError:
            main_type = 'application' # Mặc định
            sub_type = 'octet-stream'
            
        print("[Response] processing MIME main_type={} sub_type={}".format(main_type,sub_type))
        
        # <--- HOÀN THIỆN: Logic xác định thư mục
        # Gán Content-Type header
        self.headers['Content-Type'] = mime_type
        
        # [cite_start]Xác định base_dir dựa trên cấu trúc thư mục [cite: 32-38]
        if main_type == 'text':
            if sub_type == 'html':
                base_dir = os.path.join(BASE_DIR, "www")
            elif sub_type == 'css':
                base_dir = os.path.join(BASE_DIR, "static", "css")
            elif sub_type == 'javascript':
                base_dir = os.path.join(BASE_DIR, "static", "js")
            else:
                base_dir = os.path.join(BASE_DIR, "static")
        elif main_type == 'image':
            base_dir = os.path.join(BASE_DIR, "static", "images")
        elif main_type == 'application':
            if sub_type == 'javascript': # JS có thể là application/javascript
                base_dir = os.path.join(BASE_DIR, "static", "js")
            else:
                base_dir = os.path.join(BASE_DIR, "apps")
        else:
            # Cho các loại khác như audio, video
            base_dir = os.path.join(BASE_DIR, "static")
        # --- KẾT THÚC HOÀN THIỆN

        return base_dir


    def build_content(self, path, base_dir):
        """
        Loads the objects file from storage space.
        Normalize incoming path and avoid duplicating subfolders like "css/css" or "js/js".
        """
        rel = path.lstrip('/')
        rel = os.path.normpath(rel)

        base_leaf = os.path.basename(os.path.normpath(base_dir))

        # strip repeated base_leaf prefixes: "css/css/..." -> "..."
        while rel.startswith(base_leaf + os.sep) or rel == base_leaf:
            if rel == base_leaf:
                rel = ''
                break
            rel = rel[len(base_leaf) + 1:]

        if rel:
            filepath = os.path.normpath(os.path.join(base_dir, rel))
        else:
            filepath = os.path.normpath(base_dir)

        print("[Response] serving the object at location {}".format(filepath))

        try:
            if os.path.isdir(filepath):
                index_path = os.path.join(filepath, 'index.html')
                if os.path.exists(index_path):
                    filepath = index_path
                else:
                    print(f"[Response] Attempted to read directory without index: {filepath}")
                    raise FileNotFoundError

            with open(filepath, 'rb') as f:
                content = f.read()
            return len(content), content
        except FileNotFoundError:
            print(f"[Response] File not found: {filepath}")
            raise
        except IsADirectoryError:
            print(f"[Response] Attempted to read a directory: {filepath}")
            raise FileNotFoundError

    def build_response_header(self, request):
        """
        Constructs the HTTP response headers...
        """
        if not self.status_code:
            self.status_code = 200
            self.reason = "OK"

        status_line = f"HTTP/1.1 {self.status_code} {self.reason}\r\n"
        header_lines = [status_line]
        
        # Thêm các header đã set
        for key, value in self.headers.items():
            header_lines.append(f"{key}: {value}\r\n")

        # Xử lý cookies
        for cookie_name, cookie_value in self.cookies.items():
            # Cookie value từ hook có format:
            # - Simple: "admin" → Set-Cookie: username=admin
            # - With attributes: "admin; Path=/; Max-Age=3600" → Set-Cookie: username=admin; Path=/; Max-Age=3600
            # - Delete: "deleted; Max-Age=0" → Set-Cookie: auth=deleted; Max-Age=0
            
            # Luôn luôn thêm cookie_name vào đầu
            if '; ' in cookie_value:
                # Value đã có attributes (Path, HttpOnly, Max-Age, etc.)
                header_lines.append(f"Set-Cookie: {cookie_name}={cookie_value}\r\n")
            else:
                # Simple value
                header_lines.append(f"Set-Cookie: {cookie_name}={cookie_value}\r\n")

        header_lines.append(f"Content-Length: {len(self._content)}\r\n")
        header_lines.append(f"Date: {datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}\r\n")
        header_lines.append("Connection: close\r\n")
        header_lines.append("\r\n")
        
        fmt_header = "".join(header_lines)
        return fmt_header.encode('utf-8')


    def build_notfound(self):
        """
        Constructs a standard 404 Not Found HTTP response.
        ...
        """
        # <--- CẢI TIẾN: Dùng hàm build_response_header để nhất quán
        self.status_code = 404
        self.reason = "Not Found"
        self.headers['Content-Type'] = 'text/html; charset=utf-8'
        self._content = b"<html><body><p><h1>404 Not Found</h1></p></body></html>"
        
        # Gọi hàm build_header đã sửa
        header = self.build_response_header(None) 
        return header + self._content
        # --- KẾT THÚC CẢI TIẾN

    
    def build_static_filepath(self, request_path):
        """
        Build filesystem path for a static request path safely.
        Examples:
         - "/css/chat.css" -> <BASE_DIR>/static/css/chat.css
         - "js/chat.js"   -> <BASE_DIR>/static/js/chat.js
        """
        # remove leading slash and normalise to prevent duplications/traversal
        rel = request_path.lstrip('/')
        rel = os.path.normpath(rel)

        # Prevent escaping static directory
        if rel.startswith('..'):
            raise FileNotFoundError("Invalid path")

        return os.path.join(BASE_DIR, 'static', rel)

    def build_response(self, request):
        """
        Builds a full HTTP response including headers and content based on the request.
        ...
        """
        # 1. Kiểm tra xem có lỗi (do hook) đã được set chưa
        if self._has_dynamic_content:
            header = self.build_response_header(request)
            return header + self._content
        
        # Nếu là error response
        if self.status_code and self.status_code >= 400:
            header = self.build_response_header(request)
            return header + self._content
        
        # Còn lại: load file tĩnh (sử dụng MIME để chọn thư mục - www/ cho html)
        if request and request.path:
            try:
                # Xác định MIME và base_dir tương ứng
                mime_type = self.get_mime_type(request.path)
                base_dir = self.prepare_content_type(mime_type)

                # Dùng build_content để load file (trả về length, content)
                content_length, content = self.build_content(request.path, base_dir)
                self._content = content

                # Nếu prepare_content_type chưa set header chính xác, đảm bảo Content-Type
                if 'Content-Type' not in self.headers:
                    self.headers['Content-Type'] = mime_type

                if not self.status_code:
                    self.status_code = 200
                    self.reason = "OK"

                header = self.build_response_header(request)
                return header + self._content

            except (FileNotFoundError, IsADirectoryError):
                return self.build_notfound()
            except Exception as e:
                print(f"[Response] Error building response: {e}")
                import traceback
                traceback.print_exc()
                self.set_error(500, "Internal Server Error")
                header = self.build_response_header(request)
                return header + self._content

        # Fallback: empty 200
        if not self._content:
            self._content = b''
        if not self.status_code:
            self.status_code = 200
            self.reason = "OK"
        
        header = self.build_response_header(request)
        return header + self._content

    def set_cookie(self, name, value, max_age=None, path='/', httponly=True, secure=False):
        cookie_str = f"{name}={value}; Path={path}"

        if max_age:
            cookie_str += f"; Max-Age={max_age}"
        if httponly:
            cookie_str += "; HttpOnly"
        if secure:
            cookie_str += "; Secure"
        
        self.cookies[name] = cookie_str
