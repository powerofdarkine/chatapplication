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
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

import base64
from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict

class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.
    ...
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response()

    def check_authentication(self, req):
        import base64
        cookies = self.extract_cookies(req)
        auth_cookie = cookies.get('auth')

        if not auth_cookie:
            return (False, None)

        # legacy boolean token
        if auth_cookie == 'true':
            username = cookies.get('username', 'admin')
            return (True, username)

        try:
            decoded = base64.b64decode(auth_cookie).decode('utf-8')
            username, password = decoded.split(':', 1)
        except Exception:
            return (False, None)

        # Try to validate against application USERS if available
        try:
            import start_sampleapp
            USERS = getattr(start_sampleapp, 'USERS', {})
        except Exception:
            USERS = {}

        if USERS:
            if USERS.get(username) == password:
                return (True, username)
            else:
                return (False, None)
        else:
            # Fallback: accept decoded token if no USERS available
            return (True, username)

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        try: # <--- HOÀN THIỆN: Thêm try...except để xử lý lỗi
            
            # Handle the request
            # <--- CẢI TIẾN: Tăng buffer size và kiểm tra kết nối rỗng
            msg_bytes = conn.recv(8192) # 8KB buffer
            if not msg_bytes:
                print(f"[HttpAdapter] Connection from {addr} is empty. Closing.")
                return # Client kết nối rồi ngắt ngay, backend.py sẽ đóng socket
                
            msg = msg_bytes.decode('utf-8')
            # <--- KẾT THÚC CẢI TIẾN
            
            # Yêu cầu Request object phân tích msg thô
            # (Hàm này phải tự parse headers, body, và tìm 'hook')
            req.prepare(msg, routes)

            PUBLIC_PATHS = ['/login', '/login.html', '/css/', '/js/', '/images/', '/favicon.ico']

            # <--- HOÀN THIỆN TODO: Xử lý App hook
            # Handle request hook
            needs_auth = True
            for public_path in PUBLIC_PATHS:
                if req.path.startswith(public_path):
                    needs_auth = False
                    break

            if needs_auth:
                is_authenticated, username = self.check_authentication(req)

                if not is_authenticated:
                    print(f"[HttpAdapter] Unauthorized access attempt to {req.path} from {addr}")

                    accept = req.headers.get('Accept', '')
                    is_html_request = req.path in ('/', '/index.html') or 'text/html' in accept

                    if is_html_request:
                        resp.status_code = 302
                        resp.reason = "Found"
                        resp.headers['Location'] = '/login.html'
                        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
                        resp._content = b'<html><body>Redirecting to <a href="/login.html">login</a></body></html>'
                        resp._has_dynamic_content = True
                    else:
                        resp.status_code = 401
                        resp.reason = "Unauthorized"
                        resp.headers['Content-Type'] = 'text/plain'
                        resp.headers['WWW-Authenticate'] = 'Cookie realm="Login Required"'
                        resp._content = b'401 Unauthorized'
                        resp._has_dynamic_content = True

                    response = resp.build_response(req)
                    conn.sendall(response)
                    return
                else:
                    print(f"[HttpAdapter] Authenticated user '{username}' accessing {req.path}")
                    
                    req.username = username

            if req.hook:
                print(f"[HttpAdapter] hook in route-path METHOD {req.method} PATH {req.path}")
                
                # Gọi hook (hàm trong start_sampleapp.py) 
                # với dữ liệu THỰC TẾ từ request
                try:
                    hook_response_data = req.hook(
                        headers=req.headers, 
                        body=req.body,
                        username = getattr(req, 'username', None)
                    )
                    
                    # Báo cho Response object biết có dữ liệu động
                    if isinstance(hook_response_data, dict):
                        resp.set_dynamic_content(hook_response_data)
                    else:
                        # Fallback: nếu hook trả về string/bytes
                        resp._content = str(hook_response_data).encode('utf-8') if isinstance(hook_response_data, str) else hook_response_data
                
                except Exception as e:
                    print(f"[HttpAdapter] Error during hook execution: {e}")
                    import traceback
                    traceback.print_exc()
                    resp.set_error(500, "Server Error")
            
            # <--- KẾT THÚC HOÀN THIỆN TODO
            
            # Build response
            # Hàm này trong response.py sẽ tự biết:
            # 1. Ưu tiên trả về lỗi (nếu có)
            # 2. Ưu tiên trả về dữ liệu hook (nếu có)
            # 3. Cuối cùng mới tìm file tĩnh (static file)
            response = resp.build_response(req)
            
            #print(response)
            conn.sendall(response)
            
            # <--- LỖI QUAN TRỌNG: ĐÃ XÓA conn.close()
            # conn.close() # XÓA DÒNG NÀY!
            # (File backend.py sẽ tự động đóng kết nối)
            
        except Exception as e:
            print(f"[HttpAdapter] Error handling client {addr}: {e}")
            # Đừng đóng conn ở đây, hãy để backend.py xử lý

    # <--- HOÀN THIỆN: Sửa lỗi cú pháp của @property
    # Đây không phải là @property, đây là một method.
    def extract_cookies(self, req):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}
        # Lấy header 'Cookie' từ request object
        cookie_header = req.headers.get('Cookie')
        
        if cookie_header:
            for pair in cookie_header.split(";"):
                try:
                    # Tách key, value
                    key, value = pair.strip().split("=", 1)
                    cookies[key] = value
                except ValueError:
                    # Bỏ qua cookie bị lỗi (ví dụ: "mycookie" không có "=")
                    pass
        return cookies
    # <--- KẾT THÚC HOÀN THIỆN

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object 
        
        <... Ghi chú: Phần code này có vẻ bị trùng lặp 
         với logic của daemon/response.py và có thể không được 
         gọi. Logic xử lý chính nằm trong handle_client ...>
        """
        response = Response()

        # Set encoding.
        response.encoding = get_encoding_from_headers(response.headers)
        response.raw = resp
        response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        # <--- HOÀN THIỆN: Sửa lỗi gọi hàm
        response.cookies = self.extract_cookies(req) # Phải gọi self.

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    # def get_connection(self, url, proxies=None):
    # ... (phần code này không cần thiết cho bài tập)


    def add_headers(self, request):
        """
        Add headers to the request.
        ...
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 
        ...
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        username, password = ("user1", "password")

        if username:
            # <--- HOÀN THIỆN: Sửa logic dummy
            # (Dù phần này có thể không dùng đến trong bài tập)
            import base64
            auth_str = f"{username}:{password}"
            encoded_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
            headers["Proxy-Authorization"] = f"Basic {encoded_auth}"
            # <--- KẾT THÚC HOÀN THIỆN

        return headers
    
