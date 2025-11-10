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

from __future__ import annotations

import socket
import threading
from typing import Dict, Iterable, Optional, Tuple

from daemon.response import Response

from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict
from .http_consts import CRLF, CRLF2

_round_robin_global_lock = threading.Lock()
_round_robin_locks: Dict[str, threading.Lock] = {}
_round_robin_indices: Dict[str, int] = {}


def _normalize_host_for_key(host_header: str) -> str:
    """Normalize Host header to a dict key (lowercase, strip port)."""
    return host_header.split(":", 1)[0].lower().strip()

def forward_request(host: str, port: int, request: str) -> bytes:
    """Forward a raw HTTP request to a backend and return the backend response bytes.

    Args:
        host (str): Backend IP or hostname.
        port (int): Backend TCP port.
        request (str): Full HTTP request text (headers + CRLFCRLF + optional body).

    Returns:
        bytes: Raw HTTP response bytes from the backend, or a 502 response on error.
    """
    backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    backend.settimeout(5.0)
    try:
        backend.connect((host, port))
        backend.sendall(request.encode("utf-8"))
        chunks: list[bytes] = []
        while True:
            chunk = backend.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except socket.error as exc:
        print(f"[Proxy] Backend {host}:{port} socket error: {exc}")
        return Response.bad_gateway().build_response_bytes()
    finally:
        try:
            backend.close()
        except Exception:
            pass

def resolve_routing_policy(hostname: str, routes: Dict) -> Tuple[Optional[str], Optional[int]]:
    """Resolve a backend host and port for a given Host header using routing config.

    The routing table maps host keys to a dict containing "backends" and
    optional policy (e.g., "round-robin"). This function supports exact
    matches and fallback matches that ignore the client-supplied port.

    Args:
        hostname (str): Value from the Host header (may include port).
        routes (Dict): Routing configuration mapping host -> config dict.

    Returns:
        Tuple[Optional[str], Optional[int]]: (host, port) or (None, None) if not found.
    """
    # Exact match
    route_info = routes.get(hostname.lower())

    # Try without client-sent port
    if route_info is None:
        host_only = _normalize_host_for_key(hostname)
        route_info = routes.get(host_only)

        if route_info is None:
            for key, info in routes.items():
                if _normalize_host_for_key(key) == host_only:
                    route_info = info
                    print(f"[Proxy] Matched {hostname} to config key '{key}' (port-stripped)")
                    break

    if not route_info or not route_info.get("backends"):
        print(f"[Proxy] No backends configured for hostname: {hostname}")
        return None, None

    backends = route_info["backends"]
    policy = route_info.get("policy", "first")

    if len(backends) == 1:
        chosen = backends[0]

    elif policy == "round-robin":
        host_key = _normalize_host_for_key(hostname)
        
        with _round_robin_global_lock:
            if host_key not in _round_robin_locks:
                _round_robin_locks[host_key] = threading.Lock()
                _round_robin_indices[host_key] = 0
        
        with _round_robin_locks[host_key]:
            idx = _round_robin_indices[host_key]
            chosen = backends[idx]
            _round_robin_indices[host_key] = (idx + 1) % len(backends)
    
    else:
        chosen = backends[0]

    try:
        proxy_host, proxy_port_str = chosen.split(":", 1)
        return proxy_host.strip(), int(proxy_port_str.strip())
    
    except ValueError:
        print(f"[Proxy] Invalid backend format: {chosen}")
        return None, None

def handle_client(ip: str, port: int, conn: socket.socket, addr, routes: Dict) -> None:
    """Serve one client connection: parse Host header, forward to backend, return response.

    The function reads a single HTTP request from ``conn``, resolves the
    appropriate backend using :func:`resolve_routing_policy`, forwards the
    request, and writes the backend response back to the client socket.

    Args:
        ip (str): Proxy bind IP (used for logs).
        port (int): Proxy bind port (used for logs).
        conn (socket.socket): Accepted client socket.
        addr: Client address tuple.
        routes (Dict): Routing configuration.
    """
    try:
        conn.settimeout(5.0)
        request_bytes = conn.recv(8192)
        if not request_bytes:
            return

        try:
            request = request_bytes.decode("utf-8", errors="replace")
        except Exception:
            request = request_bytes.decode("iso-8859-1", errors="replace")

        try:
            header_part, body_part = request.split(CRLF2, 1)
        except ValueError:
            header_part, body_part = request, ""

        header_lines = header_part.splitlines()

        # Extract Host header (HTTP/1.1 requires Host)
        hostname: Optional[str] = None
        for line in header_lines:
            if line.lower().startswith("host:"):
                hostname = line.split(":", 1)[1].strip()
                break

        if not hostname:
            print(f"[Proxy] {addr} missing Host header")
            conn.sendall(Response.bad_request().build_response_bytes())
            return

        print(f"[Proxy] {addr} Host: {hostname}")

        # Resolve backend
        resolved_host, resolved_port = resolve_routing_policy(hostname, routes)

        if not resolved_host or not resolved_port:
            print(f"[Proxy] Unrecognized host: {hostname}")
            conn.sendall(Response.not_found().build_response_bytes())
            return

        print(f"[Proxy] Forwarding {addr} to {resolved_host}:{resolved_port}")

        modified_header_lines = []
        headers_to_set = routes.get(hostname, {}).get("headers", {})

        if not headers_to_set:
            headers_to_set = routes.get(_normalize_host_for_key(hostname), {}).get("headers", {})

        host_header_value: Optional[str] = None
        if headers_to_set.get("Host") == "$host":
            host_header_value = hostname

        client_ip = addr[0] if isinstance(addr, (list, tuple)) and len(addr) > 0 else str(addr)
        xff_added = False

        for line in header_lines:
            low = line.lower()
            if low.startswith("host:") and host_header_value:
                modified_header_lines.append(f"Host: {host_header_value}")
            elif low.startswith("x-forwarded-for:"):
                try:
                    existing = line.split(":", 1)[1].strip()
                except Exception:
                    existing = ''
                if existing:
                    modified_header_lines.append(f"X-Forwarded-For: {existing}, {client_ip}")
                else:
                    modified_header_lines.append(f"X-Forwarded-For: {client_ip}")
                xff_added = True
            else:
                modified_header_lines.append(line)

        if not xff_added:
            modified_header_lines.append(f"X-Forwarded-For: {client_ip}")

        modified_request = CRLF.join(modified_header_lines) + CRLF2 + body_part

        backend_response = forward_request(resolved_host, resolved_port, modified_request)
        conn.sendall(backend_response)

    except socket.timeout:
        print(f"[Proxy] Timeout serving {addr}")
    except Exception as exc:
        print(f"[Proxy] Error serving {addr}: {exc}")
    finally:
        try:
            conn.close()
        except Exception:
            pass

def run_proxy(ip: str, port: int, routes: Dict) -> None:
    """Run the blocking proxy server loop that accepts connections.

    Args:
        ip (str): Bind IP address (e.g., "127.0.0.1").
        port (int): Bind port (e.g., 8080).
        routes (Dict): Routing configuration (see :func:`resolve_routing_policy`).
    """
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        proxy.bind((ip, port))
        proxy.listen(50)
        print(f"[Proxy] Listening on {ip}:{port}")

        while True:
            conn, addr = proxy.accept()
            print(f"[Proxy] Accepted {addr}")
            t = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes),
                daemon=True,
            )
            t.start()

    except socket.error as exc:
        print(f"[Proxy] Socket error: {exc}")
    finally:
        try:
            proxy.close()
        except Exception:
            pass


def create_proxy(ip: str, port: int, routes: Dict) -> None:
    """Entry point for launching the proxy server."""
    run_proxy(ip, port, routes)