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
daemon.backend
~~~~~~~~~~~~~~~~~

This module provides a backend object to manage and persist backend daemon. 
It implements a basic backend server using Python's socket and threading libraries.
It supports handling multiple client connections concurrently and routing requests using a
custom HTTP adapter.

Requirements:
--------------
- socket: provide socket networking interface.
- threading: Enables concurrent client handling via threads.
- response: response utilities.
- httpadapter: the class for handling HTTP requests.
- CaseInsensitiveDict: provides dictionary for managing headers or routes.


Notes:
------
- The server create daemon threads for client handling.
- The current implementation error handling is minimal, socket errors are printed to the console.
- The actual request processing is delegated to the HttpAdapter class.

Usage Example:
--------------
>>> create_backend("127.0.0.1", 9000, routes={})

"""

import socket
import threading
import argparse

from .response import *
from .httpadapter import HttpAdapter
from .dictionary import CaseInsensitiveDict

def handle_client(ip: str, port: int, conn: socket.socket, addr: tuple, routes: dict):
    """Create an HttpAdapter and delegate handling of a client connection.

    Args:
        ip (str): Server IP address.
        port (int): Server port number.
        conn (socket.socket): Accepted client socket.
        addr (tuple): Client address (ip, port).
        routes (dict): Route handler mapping passed to the adapter.
    """
    try:
        daemon = HttpAdapter(ip, port, conn, addr, routes)
        daemon.handle_client(conn, addr, routes)

    except Exception as e:
        print(f"[Backend] Error handling client {addr}: {e}")
    finally:
        conn.close()

def run_backend(ip: str, port: int, routes: dict):
    """Start a TCP backend that accepts connections and dispatches them to threads.

    This function creates a listening socket, enables SO_REUSEADDR for fast restarts,
    and enters an accept loop. For each accepted client it spawns a daemon thread
    that calls :func:`handle_client`.

    Args:
        ip (str): IP address to bind.
        port (int): Port number to listen on.
        routes (dict): Route handlers mapping passed to each client adapter.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((ip, port))
        server.listen(50)
        print("[Backend] Listening on port {}".format(port))
        if routes != {}:
            print("[Backend] route settings {}".format(routes))

        while True:
            conn, addr = server.accept()
            print(f"[Backend] Accepted connection from {addr}")

            client_thread = threading.Thread(
                target=handle_client,
                args=(ip, port, conn, addr, routes)
            )
            client_thread.daemon = True 
            client_thread.start()
    except socket.error as e:
      print("Socket error: {}".format(e))
    except KeyboardInterrupt:
        print("\n[Backend] Server shutting down.")
    finally:
        server.close()

def create_backend(ip: str, port: int, routes: dict={}):
    """Convenience entry point that starts the backend server.

    Args:
        ip (str): Address to bind the backend server.
        port (int): Port to listen on.
        routes (dict): Optional mapping of route handlers.
    """

    run_backend(ip, port, routes)