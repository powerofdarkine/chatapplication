from dataclasses import dataclass
from typing import Dict, Optional
import re
import urllib.parse

TOKEN_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")

@dataclass
class Cookie:
  name: str
  value: str
  path: str = "/"
  max_age: Optional[int] = None
  httponly: bool = True
  secure: bool = False

  def render_set_cookie(self) -> str:
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
  out: Dict[str, str] = {}
  if not header:
    return out
  for part in header.split(";"):
    part = part.strip()
    if not part:
      continue
    if "=" in part:
      k, v = part.split("=", 1)
      k = urllib.parse.unquote(k.strip())
      v = urllib.parse.unquote(v.strip().strip('"'))
      out[k] = v
  return out

def make_set_cookie(
    name: str, 
    value: str,
    max_age: Optional[int] = None,
    path: str = "/",
    httponly: bool = True,
    secure: bool = False) -> str:
  c = Cookie(name, value, path, max_age, httponly, secure)
  return c.render_set_cookie()