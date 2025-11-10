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
deamon.weaproute
~~~~~~~~~~~~~~~~~

This module provides a WeApRous object to deploy RESTful url web app with routing
"""

from .backend import create_backend

class WeApRous:
    """The fully mutable :class:`WeApRous <WeApRous>` object, which is a lightweight,
    mutable web application router for deploying RESTful URL endpoints.

    The `WeApRous` class provides a decorator-based routing system for building simple
    RESTful web applications.  The class allows developers to register route handlers 
    using decorators and launch a TCP-based backend server to serve RESTful requests. 
    Each route is mapped to a handler function based on HTTP method and path. It mappings
    supports tracking the combined HTTP methods and path route mappings internally.

    Usage::
      >>> import daemon.weaprous
      >>> app = WeApRous()
      >>> @app.route('/login', methods=['POST'])
      >>> def login(headers="guest", body="anonymous"):
      >>>     return {'message': 'Logged in'}

      >>> @app.route('/hello', methods=['GET'])
      >>> def hello(headers, body):
      >>>     return {'message': 'Hello, world!'}

      >>> app.run()
    """

    def __init__(self):
        """Initialize an empty WeApRous application.

        Creates an empty route registry and placeholders for IP/port.
        """
        self.routes = {}
        self.ip = None
        self.port = None
        return

    def prepare_address(self, ip, port):
        """Configure bind address for the backend server.

        Args:
            ip (str): IP address to bind the server to.
            port (int): Port number to listen on.
        """
        self.ip = ip
        self.port = port

    def route(self, path, methods=['GET']):
        """
        Decorator to register a route handler for a specific path and HTTP methods.

        :param path (str): The URL path to route.
        :param methods (list): A list of HTTP methods (e.g., ['GET', 'POST']) to bind.

        :rtype: function - A decorator that registers the handler function.
        """
        def decorator(func):
            for method in methods:
                self.routes[(method.upper(), path)] = func

            # Optional attach route metadata to the function
            func._route_path = path
            func._route_methods = methods

            return func
        return decorator

    def run(self):
        """Start the backend server using the configured address.

        The method delegates to :func:`daemon.backend.create_backend` and will
        block serving requests until the process is terminated.
        """
        if not self.ip or not self.port:
            print("Rous app need to preapre address"
                  "by calling app.prepare_address(ip,port)")

        create_backend(self.ip, self.port, self.routes)
        
