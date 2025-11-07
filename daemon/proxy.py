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

# ----------------------------
# Round-robin state (thread-safe)
# ----------------------------

_round_robin_global_lock = threading.Lock()
_round_robin_locks: Dict[str, threading.Lock] = {}
_round_robin_indices: Dict[str, int] = {}


def _normalize_host_for_key(host_header: str) -> str:
    """Normalize Host header to a dict key (lowercase, strip port)."""
    return host_header.split(":", 1)[0].lower().strip()


# ----------------------------
# Backend forwarding
# ----------------------------

def forward_request(host: str, port: int, request: str) -> bytes:
    """Forward a raw HTTP request to a backend and return raw HTTP response bytes.

    Inputs:
        - host (str): backend IP/hostname.
        - port (int): backend TCP port.
        - request (str): full HTTP request (headers + CRLFCRLF + optional body).

    Outputs:
        - bytes: raw HTTP response from backend.
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


# ----------------------------
# Routing / policy resolution
# ----------------------------

def resolve_routing_policy(hostname: str, routes: Dict) -> Tuple[Optional[str], Optional[int]]:
    """Resolve (host, port) for a given HTTP Host header using routes and policy.

    Inputs:
        - hostname (str): value from Host header (may include port).
        - routes (dict): per-host config like:
            routes = {
              "app.local": {
                 "backends": ["127.0.0.1:9001", "127.0.0.1:9002"],
                 "policy": "round-robin",
                 "headers": {"Host": "$host"}
              },
              ...
            }

    Outputs:
        - (host, port) or (None, None) if not found/invalid.
    """
    # Exact match
    route_info = routes.get(hostname.lower())

    # Try without client-sent port
    if route_info is None:
        host_only = _normalize_host_for_key(hostname)
        route_info = routes.get(host_only)

        # Fuzzy: compare host part of keys (ignore port)
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

    # Single backend: choose it
    if len(backends) == 1:
        chosen = backends[0]
    # Round-robin across multiple backends (thread-safe per host-key)
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


# ----------------------------
# Client handling
# ----------------------------

def handle_client(ip: str, port: int, conn: socket.socket, addr, routes: Dict) -> None:
    """Handle a single client connection: read request, route, forward, return.

    Inputs:
        - ip (str): proxy bind IP (for logs only).
        - port (int): proxy bind port (for logs only).
        - conn (socket.socket): accepted client socket.
        - addr: client address tuple.
        - routes (dict): routing configuration.
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

        # Split headers/body
        try:
            header_part, body_part = request.split("\r\n\r\n", 1)
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

        # Optionally override/propagate headers from config
        modified_header_lines = []
        headers_to_set = routes.get(hostname, {}).get("headers", {})
        # If config uses key without port, also check that entry
        if not headers_to_set:
            headers_to_set = routes.get(_normalize_host_for_key(hostname), {}).get("headers", {})

        host_header_value: Optional[str] = None
        if headers_to_set.get("Host") == "$host":
            host_header_value = hostname

        for line in header_lines:
            if line.lower().startswith("host:") and host_header_value:
                modified_header_lines.append(f"Host: {host_header_value}")
            else:
                modified_header_lines.append(line)

        modified_request = "\r\n".join(modified_header_lines) + "\r\n\r\n" + body_part

        # Forward and return response to client
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


# ----------------------------
# Server bootstrap
# ----------------------------

def run_proxy(ip: str, port: int, routes: Dict) -> None:
    """Run the proxy server loop (blocking).

    Inputs:
        - ip (str): bind IP (e.g., "127.0.0.1").
        - port (int): bind port (e.g., 8080).
        - routes (dict): routing configuration (see resolve_routing_policy doc).
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