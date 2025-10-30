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
daemon.proxy
~~~~~~~~~~~~~~~~~

This module implements a simple proxy server using Python's socket and threading libraries.
It routes incoming HTTP requests to backend services based on hostname mappings and returns
the corresponding responses to clients.

Requirement:
-----------------
- socket: provides socket networking interface.
- threading: enables concurrent client handling via threads.
- response: customized :class: `Response <Response>` utilities.
- httpadapter: :class: `HttpAdapter <HttpAdapter >` adapter for HTTP request processing.
- dictionary: :class: `CaseInsensitiveDict <CaseInsensitiveDict>` for managing headers and cookies.

"""
import socket
import threading
from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

# <--- HOÀN THIỆN: Thêm các lock để xử lý Round Robin thread-safe --->
# Lock để bảo vệ khi thêm một host mới vào `round_robin_locks`
round_robin_global_lock = threading.Lock()
# Dictionary chứa các lock riêng cho từng host, để bảo vệ index của host đó
round_robin_locks = {}
# Dictionary chứa index hiện tại của từng host
round_robin_indices = {}
# <--- KẾT THÚC HOÀN THIỆN --->


def forward_request(host, port, request):
    """
    Forwards an HTTP request to a backend server and retrieves the response.

    :params host (str): IP address of the backend server.
    :params port (int): port number of the backend server.
    :params request (str): incoming HTTP request.

    :rtype bytes: Raw HTTP response from the backend server. If the connection
                    fails, returns a 404 Not Found response.
    """

    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    backend.settimeout(5.0) # <--- CẢI TIẾN: Thêm timeout để tránh bị treo

    try:
        backend.connect((host, port))
        backend.sendall(request.encode('utf-8')) # <--- HOÀN THIỆN: Chỉ định encoding
        response = b""
        while True:
            chunk = backend.recv(4096)
            if not chunk:
                break
            response += chunk
        return response
    except socket.error as e:
        print(f"Socket error forwarding to {host}:{port}: {e}")
        return (
            "HTTP/1.1 502 Bad Gateway\r\n" # 502 thì đúng hơn 404
            "Content-Type: text/plain\r\n"
            "Content-Length: 15\r\n"
            "Connection: close\r\n"
            "\r\n"
            "502 Bad Gateway"
        ).encode('utf-8')
    finally:
        backend.close() # <--- HOÀN THIỆN: Luôn đóng socket


def resolve_routing_policy(hostname, routes):
    """
    Handles an routing policy to return the matching proxy_pass.
    It determines the target backend to forward the request to.

    :params hostname (str): IP address of the request target server.
    :params routes (dict): dictionary mapping hostnames and location.
    
    :rtype tuple: (host, port) or (None, None) if not found
    """

    # <--- BẮT ĐẦU TÍCH HỢP LOGIC CỦA BẠN ---
    
    # Thử 1: Tìm chính xác (không phân biệt hoa thường)
    # Ví dụ: Host header là 'app2.local', config key là 'app2.local'
    route_info = routes.get(hostname.lower())

    # Thử 2: Nếu không thấy, thử tìm 'app2.local' khi Host header là 'app2.local:8080'
    if route_info is None:
        host_only = hostname.split(':', 1)[0].lower()
        
        # Thử tìm chính xác 'host_only' (ví dụ: 'app2.local')
        route_info = routes.get(host_only)

        # Thử 3: Nếu vẫn không thấy, dùng logic "fuzzy" của bạn
        # (để xử lý trường hợp config key là '192.168.56.103:8080')
        if route_info is None:
            for key, info in routes.items():
                # So sánh phần host (đã bỏ port) của key trong config
                # với phần host (đã bỏ port) của Host header
                if key.lower().split(':', 1)[0] == host_only:
                    route_info = info
                    print(f"[Proxy] Matched {hostname} to config key {key} (port-stripped)")
                    break
    
    # <--- KẾT THÚC TÍCH HỢP ---

    # Trường hợp 1: Không tìm thấy host hoặc host không có backend
    if not route_info or not route_info.get('backends'):
        print(f"[Proxy] No backends configured for hostname: {hostname}")
        return (None, None)

    backends = route_info['backends']
    policy = route_info['policy']
    chosen_backend_str = ""

    # Trường hợp 2: Chỉ có 1 backend, không cần policy
    if len(backends) == 1:
        chosen_backend_str = backends[0]
        
    # Trường hợp 3: Có nhiều backend, áp dụng policy
    elif policy == 'round-robin':
        # --- Bắt đầu vùng critical (cần thread-safe) ---
        
        # Kiểm tra xem đã có lock cho host này chưa, nếu chưa thì tạo
        with round_robin_global_lock:
            if hostname not in round_robin_locks:
                round_robin_locks[hostname] = threading.Lock()
                round_robin_indices[hostname] = 0

        # Dùng lock của riêng host này để lấy/cập nhật index
        with round_robin_locks[hostname]:
            current_index = round_robin_indices[hostname]
            chosen_backend_str = backends[current_index]
            
            # Cập nhật index cho lần gọi tiếp theo
            round_robin_indices[hostname] = (current_index + 1) % len(backends)
        # --- Kết thúc vùng critical ---

    # Trường hợp 4: Policy không được hỗ trợ hoặc mặc định
    else:
        chosen_backend_str = backends[0] # Mặc định lấy cái đầu tiên
        
    # Tách host và port từ chuỗi backend
    try:
        proxy_host, proxy_port_str = chosen_backend_str.split(":", 1)
        proxy_port = int(proxy_port_str)
        return (proxy_host, proxy_port)
    except ValueError:
        print(f"[Proxy] Invalid backend format: {chosen_backend_str}")
        return (None, None)

def handle_client(ip, port, conn, addr, routes):
    """
    Handles an individual client connection by parsing the request...
    """

    try:
        # <--- CẢI TIẾN: Tăng buffer size và thêm timeout
        conn.settimeout(5.0)
        request_bytes = conn.recv(8192) # 8KB buffer
        if not request_bytes:
            conn.close()
            return
            
        request = request_bytes.decode('utf-8')
        # <--- KẾT THÚC CẢI TIẾN
        
        hostname = None # <--- HOÀN THIỆN: Khởi tạo
        
        # Tách header và body
        try:
            header_part, body_part = request.split("\r\n\r\n", 1)
        except ValueError:
            header_part = request
            body_part = ""

        header_lines = header_part.splitlines()
        
        # Extract hostname
        for line in header_lines:
            if line.lower().startswith('host:'):
                hostname = line.split(':', 1)[1].strip()
                break # Tìm thấy là thoát

        if not hostname:
            print(f"[Proxy] {addr} sent request with no Host header. Closing.")
            # HTTP/1.1 yêu cầu phải có Host header
            response = (
                "HTTP/1.1 400 Bad Request\r\n"
                "Content-Length: 15\r\n\r\n"
                "400 Bad Request"
            ).encode('utf-8')
            conn.sendall(response)
            conn.close()
            return

        print(f"[Proxy] {addr} requesting Host: {hostname}")

        # Resolve the matching destination
        resolved_host, resolved_port = resolve_routing_policy(hostname, routes)

        # <--- HOÀN THIỆN: Xử lý 404 nếu không resolve được
        if not resolved_host:
            print(f"[Proxy] Host name {hostname} not recognized or configured.")
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/plain\r\n"
                "Content-Length: 13\r\n"
                "Connection: close\r\n"
                "\r\n"
                "404 Not Found"
            ).encode('utf-8')
        
        else:
            print(f"[Proxy] Host {hostname} forwarded to {resolved_host}:{resolved_port}")

            # <--- HOÀN THIỆN: Triển khai proxy_set_header
            modified_request_lines = []
            headers_to_set = routes.get(hostname, {}).get('headers', {})
            host_header_value = None

            if 'Host' in headers_to_set and headers_to_set['Host'] == '$host':
                host_header_value = hostname # $host nghĩa là hostname client request

            for line in header_lines:
                # Nếu config yêu cầu set Host header, ta thay thế nó
                if line.lower().startswith('host:') and host_header_value:
                    modified_request_lines.append(f"Host: {host_header_value}")
                else:
                    modified_request_lines.append(line)
            
            # Ghép lại request đã chỉnh sửa
            modified_header_part = "\r\n".join(modified_request_lines)
            modified_request = modified_header_part + "\r\n\r\n" + body_part
            # <--- KẾT THÚC HOÀN THIỆN HEADER

            response = forward_request(resolved_host, resolved_port, modified_request)
        
        conn.sendall(response)

    except socket.timeout:
        print(f"[Proxy] Connection timed out for {addr}")
    except Exception as e:
        print(f"[Proxy] Error handling client {addr}: {e}")
    finally:
        conn.close()


def run_proxy(ip, port, routes):
    """
    Starts the proxy server and listens for incoming connections. 
    ...
    """

    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # <--- CẢI TIẾN

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print(f"[Proxy] Listening on IP {ip} port {port}")
        while True:
            conn, addr = proxy.accept()
            print(f"[Proxy] Accepted connection from {addr}") # <--- Thêm log
            
            # <--- HOÀN THIỆN: Triển khai multi-thread
            # 
            # Dụng ý của giáo viên là dùng thread để xử lý đồng thời
            # nhiều kết nối.
            #
            client_thread = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes)
            )
            client_thread.daemon = True # Tự động tắt thread khi chương trình chính tắt
            client_thread.start()
            # <--- KẾT THÚC HOÀN THIỆN
            
    except socket.error as e:
        print(f"Socket error: {e}")
    finally:
        proxy.close() # <--- HOÀN THIỆN: Đóng socket khi kết thúc

def create_proxy(ip, port, routes):
    """
    Entry point for launching the proxy server.

    :params ip (str): IP address to bind the proxy server.
    :params port (int): port number to listen on.
    :params routes (dict): dictionary mapping hostnames and location.
    """

    run_proxy(ip, port, routes)