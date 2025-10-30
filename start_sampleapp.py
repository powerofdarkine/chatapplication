#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course,
# and is released under the "MIT License Agreement". Please see the LICENSE
# file that should have been included as part of this package.
#
# WeApRous release
#
# The authors hereby grant to Licensee personal permission to use
# and modify the Licensed Source Code for the sole purpose of studying
# while attending the course
#


"""
start_sampleapp
~~~~~~~~~~~~~~~~~

This module provides a sample RESTful web application using the WeApRous framework.

It defines basic route handlers and launches a TCP-based backend server to serve
HTTP requests. The application includes a login endpoint and a greeting endpoint,
and can be configured via command-line arguments.
"""

import json
import socket
import base64
import os
from urllib.parse import parse_qs
import argparse

from daemon.weaprous import WeApRous

PORT = 9001  # Default port

app = WeApRous()

USERS = {
    'admin' : 'password',
    'user1' : 'pass123',
    'user2' : 'pass456'
}

@app.route('/login', methods=['POST'])
def handle_login(headers, body, username=None):
    """
    Handle user login via POST request.

    This route simulates a login process and prints the provided headers and body
    to the console.

    :param headers (str): The request headers or user identifier.
    :param body (str): The request body or login payload.
    """
    print("[SampleApp] Logging in {} to {}".format(headers, body))

    params = {}
    if body:
        for pair in body.split('&'):
            try:
                key, value = pair.split('=', 1)
                from urllib.parse import unquote
                params[unquote(key)] = unquote(value)
            except ValueError:
                pass

    username = params.get('username', '').strip()
    password = params.get('password', '').strip()

    print(f"[SampleApp] Login attemp - username: '{username}'")

    if username in USERS and USERS[username] == password:
        print(f"[SampleApp] Login Success for '{username}'")

        auth_token = base64.b64encode(f"{username}:{password}".encode()).decode()

        return {
            'status': 302,
            'headers' : {
                'Location': '/',
                'Content-Type': 'text/html; charset=utf-8'
            },
            'cookies': {
                'auth': f"{auth_token}; Path=/; HttpOnly; Max-Age=3600",
                'username': f"{username}; Path=/; Max-Age=3600"
            },
            'body': '<html><body>Redirecting...</body></html>'
        }
    else:
        print(f"[SampleApp] Login Failed for '{username}'")

        error_html = load_html('login_error.html')

        return {
            'status': 401,
            'headers': {
                'Content-Type': 'text/html; charset=utf-8',
                'WWW-Authenticate': 'Form realm="Login Required"'
            },
            'body': error_html
        }

@app.route('/logout', methods=['GET', 'POST'])
def handle_logout(headers, body, username=None):
    """
    Handle logout - clear cookies and redirect to login.
    """
    print(f"[SampleApp] Logout for user '{username}'")
    
    return {
        'status': 302,
        'headers': {
            'Location': '/login.html',
            'Content-Type': 'text/html; charset=utf-8'
        },
        'cookies': {
            'auth': 'deleted; Max-Age=0',
            'username': 'deleted; Max-Age=0'
        },
        'body': '<html><body>Logging out...</body></html>'
    }

@app.route('/api/user', methods=['GET'])
def get_user_info(headers, body, username=None):
    """
    API endpoint - return current user info (for Task 2 P2P chat).
    Requires authentication.
    """
    return {
        'status': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({
            'username': username,
            'authenticated': True,
            'timestamp': __import__('datetime').datetime.utcnow().isoformat()
        })
    }

@app.route('/api/peers', methods=['GET'])
def get_peers(headers, body, username=None):
    """
    API endpoint - return list of online peers (stub for Task 2).
    """
    # TODO: Implement peer tracking
    peers = ['user1', 'user2', 'admin']
    if username in peers:
        peers.remove(username)
    
    return {
        'status': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({'peers': peers})
    }

@app.route('/api/message', methods=['POST'])
def send_message(headers, body, username=None):
    """
    API endpoint - send P2P message (stub for Task 2).
    """
    print(f"[SampleApp] Message from {username}: {body}")
    
    # TODO: Implement P2P message routing
    
    return {
        'status': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps({'status': 'sent', 'from': username})
    }


def load_html(filename):
    """
    Helper function to load HTML files.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    filename = filename.replace('./', '').replace('www/', '')
    
    # Build full path
    filepath = os.path.join(base_dir, 'www', filename)
    
    print(f"[SampleApp] Loading HTML from: {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"[SampleApp] ✓ Loaded {len(content)} bytes from {filename}")
            return content
    except FileNotFoundError:
        print(f"[SampleApp] ✗ File not found: {filepath}")
        return f'<html><body><h1>Error</h1><p>File {filename} not found at {filepath}</p></body></html>'
    except Exception as e:
        print(f"[SampleApp] ✗ Error loading {filename}: {e}")
        return f'<html><body><h1>Error</h1><p>Error loading {filename}: {e}</p></body></html>'


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='SampleApp',
        description='WeApRous sample application with authentication',
        epilog='Task 1 & 2 implementation'
    )
    parser.add_argument('--server-ip', default='127.0.0.1')
    parser.add_argument('--server-port', type=int, default=PORT)
 
    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    print(f"[SampleApp] Starting on {ip}:{port}")
    print(f"[SampleApp] Available users: {list(USERS.keys())}")
    
    app.prepare_address(ip, port)
    app.run()