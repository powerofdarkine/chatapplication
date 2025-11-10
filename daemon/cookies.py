"""
daemon.cookies -- small utilities for HTTP cookie handling.

Provides:
- Cookie dataclass for response cookies and rendering a Set-Cookie header value.
- parse_cookie_header(header) -> Dict[str, str] to parse client "Cookie" headers.
- make_set_cookie(...) convenience helper to build a Set-Cookie string.

Design notes:
- Client cookies are parsed into simple dict[str, str].
- Response cookies are represented by Cookie objects to hold attributes (Path, Max-Age, HttpOnly, Secure).
- Parsing avoids fragile heuristics and validates token names.
"""
from dataclasses import dataclass
from typing import Dict, Optional
import re
import urllib.parse

TOKEN_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")

@dataclass
class Cookie:
  """Representation of an HTTP response cookie.

  Attributes:
      name (str): Cookie name.
      value (str): Cookie value (unquoted string).
      path (str): Path attribute (defaults to '/').
      max_age (Optional[int]): Max-Age in seconds, or None.
      httponly (bool): HttpOnly flag.
      secure (bool): Secure flag.

  Methods:
      render_set_cookie(): Return the Set-Cookie header value for this cookie.
  """
  name: str
  value: str
  path: str = "/"
  max_age: Optional[int] = None
  httponly: bool = True
  secure: bool = False

  def render_set_cookie(self) -> str:
    """Render the cookie as a Set-Cookie header value (without the header name)."""
    name = self.name
    val = self.value
    if not TOKEN_RE.match(val):
      val = '"' + val.replace('"', '\\"') +'"'
    parts = [f"{name}={val}"]
    if self.path:
      parts.append(f"Path={self.path}")
    if self.max_age is not None:
      parts.append(f"Max-Age={int(self.max_age)}")
    if self.secure:
      parts.append("Secure")
    if self.httponly:
      parts.append("HttpOnly")
    return "; ".join(parts)
  
def parse_cookie_header(header: Optional[str]) -> Dict[str, str]:
  """Parse a `Cookie` header string into a mapping of names to values.

  The parser is conservative: malformed segments are skipped and reported
  via print statements. Percent-encoding and surrounding quotes are
  unescaped for values.

  Args:
      header (Optional[str]): Raw Cookie header value.

  Returns:
      Dict[str, str]: Mapping cookie name -> value.
  """
  out: Dict[str, str] = {}
  if not header:
    return out
  for part in header.split(";"):
    part = part.strip()
    if not part:
      continue
    # Require explicit '=' to avoid fragile heuristics. Log and skip invalid parts.
    if "=" not in part:
      print(f"[cookies] Skipping invalid cookie segment: '{part}'")
      continue

    k, v = part.split("=", 1)
    k = urllib.parse.unquote(k.strip())
    v = urllib.parse.unquote(v.strip().strip('"'))

    # Validate name token
    if not TOKEN_RE.match(k):
      print(f"[cookies] Invalid cookie name token skipped: '{k}'")
      continue

    out[k] = v
  return out

def make_set_cookie(
    name: str, 
    value: str,
    max_age: Optional[int] = None,
    path: str = "/",
    httponly: bool = True,
    secure: bool = False) -> str:
  """Create a Cookie object and return its Set-Cookie header value.

  Args:
      name (str): Cookie name.
      value (str): Cookie value.
      max_age (Optional[int]): Max-Age attribute in seconds.
      path (str): Path attribute.
      httponly (bool): HttpOnly flag.
      secure (bool): Secure flag.

  Returns:
      str: Formatted Set-Cookie header value (without the header name).
  """
  c = Cookie(name, value, path, max_age, httponly, secure)
  return c.render_set_cookie()