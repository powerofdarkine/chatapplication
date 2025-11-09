"""HTTP-related constants used across the daemon.

Keep common protocol tokens and header names here to avoid scattered
literal strings in the codebase.
"""
from datetime import timezone

# Line separators
CRLF = "\r\n"
CRLF2 = CRLF + CRLF
NLINE = "\n"
NLINE2 = NLINE + NLINE

# Protocol
HTTP_1_1 = "HTTP/1.1"

# Common header names
HEADER_SET_COOKIE = "Set-Cookie"
HEADER_CONTENT_LENGTH = "Content-Length"
HEADER_CONNECTION = "Connection"
HEADER_LOCATION = "Location"
HEADER_CONTENT_TYPE = "Content-Type"
HEADER_WWW_AUTHENTICATE = "WWW-Authenticate"

# Common header values
CONNECTION_CLOSE = "close"

# Date formatting for Date header (RFC 1123/2822 style)
DATE_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"
