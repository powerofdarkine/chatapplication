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
import socket
from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict
from .http_consts import HEADER_CONTENT_TYPE, HEADER_LOCATION, HEADER_WWW_AUTHENTICATE

class HttpAdapter:
    """HTTP adapter that handles client connections and dispatches requests.

    The adapter reads raw HTTP requests from a socket, parses them into
    :class:`Request` objects, performs optional authentication, invokes
    registered route hooks, and sends back a :class:`Response`.

    Attributes:
        ip (str): Server IP address.
        port (int): Server port.
        conn (socket.socket): Active client socket.
        connaddr (tuple): Client address.
        routes (dict): Route handlers mapping.
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

    def __init__(self, ip: str, port: int, conn: socket, connaddr: tuple, routes: dict):
        """Initialize a new HttpAdapter.

        Args:
            ip (str): IP address of the server.
            port (int): Port number of the server.
            conn (socket.socket): Active socket connection.
            connaddr (tuple): Address of the connected client.
            routes (dict): Mapping of route paths to handler functions.
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
        """Validate authentication token found in request cookies.

        The method expects an "auth" cookie containing either a legacy
        boolean marker ("true") or a base64-encoded "username:password"
        string. When an application-level `USERS` mapping is present in
        `start_sampleapp`, credentials are validated against it.

        Args:
            req (Request): Parsed request object.

        Returns:
            tuple[bool, Optional[str]]: (is_authenticated, username_or_None)
        """
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

    def handle_client(self, conn: socket, addr:tuple, routes: dict):
        """Process a single client connection.

        Reads raw bytes from ``conn``, decodes and parses them into a
        :class:`Request`, optionally enforces authentication, executes the
        matched route hook (if any), builds a :class:`Response`, and sends the
        response bytes back to the client.

        Args:
            conn (socket.socket): The client socket connection.
            addr (tuple): The client's address (ip, port).
            routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        try:
            
            # Handle the request
            msg_bytes = conn.recv(8192) # 8KB buffer
            if not msg_bytes:
                print(f"[HttpAdapter] Connection from {addr} is empty. Closing.")
                return
                
            msg = msg_bytes.decode('utf-8')
            
            req.prepare(msg, routes)

            PUBLIC_PATHS = ['/login', '/login.html', '/css/', '/js/', '/images/', '/favicon.ico']

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
                        resp.headers[HEADER_LOCATION] = '/login.html'
                        resp.headers[HEADER_CONTENT_TYPE] = 'text/html; charset=utf-8'
                        resp._content = b'<html><body>Redirecting to <a href="/login.html">login</a></body></html>'
                        resp._has_dynamic_content = True
                    else:
                        resp.status_code = 401
                        resp.reason = "Unauthorized"
                        resp.headers[HEADER_CONTENT_TYPE] = 'text/plain'
                        resp.headers[HEADER_WWW_AUTHENTICATE] = 'Cookie realm="Login Required"'
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
                
                try:
                    hook_response_data = req.hook(
                        headers=req.headers, 
                        body=req.body,
                        username = getattr(req, 'username', None)
                    )
                    
                    if isinstance(hook_response_data, dict):
                        resp.set_dynamic_content(hook_response_data)
                    else:
                        resp._content = str(hook_response_data).encode('utf-8') if isinstance(hook_response_data, str) else hook_response_data
                
                except Exception as e:
                    print(f"[HttpAdapter] Error during hook execution: {e}")
                    import traceback
                    traceback.print_exc()
                    resp.set_error(500, "Server Error")
            
            response = resp.build_response(req)
            
            conn.sendall(response)
            
        except Exception as e:
            print(f"[HttpAdapter] Error handling client {addr}: {e}")

    def extract_cookies(self, req: Request):
        """Return parsed cookies from a Request.

        Args:
            req (Request): Parsed request object.

        Returns:
            dict: Mapping of cookie name to value.
        """
        return getattr(req, 'cookies', {}) or {}
    
    def build_response(self, req: Request, resp: Response):
        """Build an adapter-level Response wrapper for a request/response pair.

        The method composes an adapter-side response object that links the
        originating request and the lower-level ``resp`` object produced by
        application hooks.

        Args:
            req (Request): The incoming request.
            resp (Response): The response produced by a handler.

        Returns:
            Response: A new Response instance wired to the adapter/context.
        """
        def get_encoding_from_headers(self, res):
            return
        response = Response()

        response.encoding = get_encoding_from_headers(response.headers)
        response.raw = resp
        response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        response.request = req
        response.connection = self

        return response

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
        username, password = ("user1", "password")

        if username:
            import base64
            auth_str = f"{username}:{password}"
            encoded_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
            headers["Proxy-Authorization"] = f"Basic {encoded_auth}"

        return headers
    
