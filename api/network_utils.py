"""
Network utilities for CIDR checks.
"""

from __future__ import annotations

import ipaddress


def is_ip_in_cidrs(ip: str, cidrs: list[str]) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for cidr in cidrs:
        try:
            if address in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False
