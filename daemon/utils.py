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

from urllib.parse import urlparse, unquote

def get_auth_from_url(url: str) -> tuple[str, str]:
    """Extract basic auth credentials from a URL.

    Parses the supplied URL and returns a (username, password) tuple. If the
    URL contains no credentials, returns ('', ''). Values are URL-unquoted.

    Args:
        url (str): URL possibly containing credentials (e.g. "http://user:pass@host/").

    Returns:
        tuple[str, str]: (username, password) or ('', '') when absent.
    """
    parsed = urlparse(url)

    try:
        auth = (unquote(parsed.username), unquote(parsed.password))
    except (AttributeError, TypeError):
        auth = ("", "")

    return auth