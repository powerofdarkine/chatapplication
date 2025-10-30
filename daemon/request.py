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
from .dictionary import CaseInsensitiveDict

class Request():
    """The fully mutable "class" `Request <Request>` object,
    ...
    """
    __attrs__ = [
        "method",
        "url",
        "headers",
        "body",
        "reason",
        "cookies",
        "body",
        "routes",
        "hook",
    ]

    def __init__(self):
        #: HTTP verb to send to the server.
        self.method = None
        #: HTTP URL to send the request to.
        self.url = None
        #: dictionary of HTTP headers.
        # <--- HOÀN THIỆN: Khởi tạo là CaseInsensitiveDict
        self.headers = CaseInsensitiveDict() 
        #: HTTP path
        self.path = None        
        # The cookies set used to create Cookie header
        self.cookies = {} # <--- HOÀN THIỆN: Khởi tạo là dict
        #: request body to send to the server.
        self.body = None
        #: Routes
        self.routes = {}
        #: Hook point for routed mapped-path
        self.hook = None

    def extract_request_line(self, first_line):
        """
        Parses the first line of an HTTP request.
        :param first_line (str): The raw request line (e.g., "GET /path HTTP/1.1")
        """
        try:
            # <--- HOÀN THIỆN: Sửa logic để chỉ xử lý 1 dòng
            method, path, version = first_line.split()

            if path == '/':
                path = '/index.html' # Mặc định trỏ / về index.html
            
            return method, path, version
        except Exception as e:
            print(f"[Request] Error parsing request line '{first_line}': {e}")
            return None, None, None
            
    def prepare_headers(self, header_lines_list):
        """
        Prepares the given HTTP headers from a list of strings.
        :param header_lines_list (list): A list of raw header strings.
        """
        headers = CaseInsensitiveDict() # <--- HOÀN THIỆN
        
        # <--- HOÀN THIỆN: Sửa logic để xử lý một list các dòng header
        for line in header_lines_list:
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key] = val # Tự động là case-insensitive
        return headers

    def prepare(self, request, routes=None):
        """Prepares the entire request with the given parameters."""

        # <--- HOÀN THIỆN: Viết lại toàn bộ logic phân tích (parsing)
        
        # 1. Tách Header Block và Body
        # Dấu hiệu kết thúc header là 2 lần xuống dòng
        try:
            header_block, self.body = request.split('\r\n\r\n', 1)
        except ValueError:
            # Nếu không có body, gán body là chuỗi rỗng
            header_block = request
            self.body = ""

        # 2. Tách Request Line và các Header
        header_lines = header_block.splitlines()
        first_line = header_lines[0]
        other_header_lines = header_lines[1:] # Các dòng header thực sự

        # 3. Phân tích Request Line
        self.method, self.path, self.version = self.extract_request_line(first_line)
        if not self.method:
            print("[Request] Could not parse request line. Aborting.")
            return

        print("[Request] {} path {} version {}".format(self.method, self.path, self.version))

        # 4. Phân tích Headers
        self.headers = self.prepare_headers(other_header_lines)
        
        # 5. Phân tích Cookies (TODO)
        cookie_string = self.headers.get('Cookie') # Dùng .get() để tránh lỗi
        if cookie_string:
            for pair in cookie_string.split(';'):
                pair = pair.strip()
                if '=' in pair:
                    key, val = pair.split('=', 1) # Tách ở dấu = đầu tiên
                    self.cookies[key] = val
        
        # 6. Tìm Hook (TODO)
        # @bksysnet Preapring the webapp hook with WeApRous instance
        # The default behaviour with HTTP server is empty routed
        #
        if routes: # routes không rỗng (tức là đang chạy WeApRous)
            self.routes = routes
            # Tìm hook dựa trên (METHOD, PATH)
            self.hook = routes.get((self.method, self.path))
            #
            # self.hook manipulation goes here
            # (Không cần làm gì thêm, self.hook giờ đã là
            #  hàm 'login' hoặc 'hello' trong start_sampleapp.py)
            #
        # --- KẾT THÚC HOÀN THIỆN ---

        return

    # --- Các hàm bên dưới dường như là "di sản" (artifact) ---
    # --- từ một thư viện client (như 'requests') và không   ---
    # --- thực sự cần thiết cho việc *parsing* một request   ---
    # --- của server. Chúng ta có thể bỏ qua các TODO ở đây. ---
    
    def prepare_body(self, data, files, json=None):
        # self.prepare_content_length(self.body)
        # self.body = body # Biến body không được định nghĩa
        #
        # TODO prepare the request authentication
        #
    # self.auth = ...
        return


    def prepare_content_length(self, body):
        # self.headers["Content-Length"] = "0"
        #
        # TODO prepare the request authentication
        #
    # self.auth = ...
        return


    def prepare_auth(self, auth, url=""):
        #
        # TODO prepare the request authentication
        #
    # self.auth = ...
        return

    def prepare_cookies(self, cookies):
            self.headers["Cookie"] = cookies