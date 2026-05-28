#!/usr/bin/env python3
"""Shared URL validation for outbound SEO audit fetches.

The audit scripts fetch user-supplied URLs. Keep all network entry points on
one validation path so private networks and metadata endpoints cannot be hit
through URL parser edge cases, obfuscated IPv4, or redirect rebinding.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlparse, urlunparse


ALLOWED_SCHEMES = {"http", "https"}
_MAX_REDIRECT_VALIDATION_HOPS = 10


@dataclass
class UrlSafetyResult:
    ok: bool
    url: str
    normalized_url: str = ""
    reason: str = ""
    hostname: str = ""
    resolved_ips: list[str] = field(default_factory=list)


def normalize_url(url: str) -> str:
    """Return a URL with default https:// and a normalized hostname."""
    value = (url or "").strip()
    if not value:
        return value
    parsed = urlparse(value)
    if not parsed.scheme:
        value = f"https://{value}"
        parsed = urlparse(value)
    if not parsed.hostname:
        return value

    host = parsed.hostname.rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        # validate_url will return a clear failure for the original hostname.
        host = parsed.hostname.rstrip(".").lower()

    netloc = host
    if parsed.port is not None:
        netloc = f"{host}:{parsed.port}"
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo = f"{userinfo}:{parsed.password}"
        netloc = f"{userinfo}@{netloc}"

    return urlunparse(
        (parsed.scheme.lower(), netloc, parsed.path or "/", parsed.params, parsed.query, parsed.fragment)
    )


def _parse_int_piece(piece: str) -> int:
    if piece.lower().startswith("0x"):
        return int(piece, 16)
    if len(piece) > 1 and piece.startswith("0") and piece.isdigit():
        return int(piece, 8)
    return int(piece, 10)


def _parse_ipv4_variant(host: str) -> ipaddress.IPv4Address | None:
    """Parse common obfuscated IPv4 forms such as decimal, hex, and octal."""
    try:
        return ipaddress.IPv4Address(host)
    except ValueError:
        pass

    try:
        if host.isdigit() or host.lower().startswith("0x"):
            value = _parse_int_piece(host)
            if 0 <= value <= 0xFFFFFFFF:
                return ipaddress.IPv4Address(value)
    except ValueError:
        return None

    pieces = host.split(".")
    if not 1 < len(pieces) <= 4:
        return None

    try:
        nums = [_parse_int_piece(piece) for piece in pieces]
    except ValueError:
        return None

    if any(num < 0 or num > 255 for num in nums[:-1]):
        return None

    if len(nums) == 2:
        if nums[1] > 0xFFFFFF:
            return None
        value = (nums[0] << 24) + nums[1]
    elif len(nums) == 3:
        if nums[2] > 0xFFFF:
            return None
        value = (nums[0] << 24) + (nums[1] << 16) + nums[2]
    else:
        if nums[3] > 255:
            return None
        value = (nums[0] << 24) + (nums[1] << 16) + (nums[2] << 8) + nums[3]

    if 0 <= value <= 0xFFFFFFFF:
        return ipaddress.IPv4Address(value)
    return None


def _host_literal_ip(host: str) -> ipaddress._BaseAddress | None:
    cleaned = host.strip("[]").rstrip(".")
    ipv4 = _parse_ipv4_variant(cleaned)
    if ipv4:
        return ipv4
    try:
        return ipaddress.ip_address(cleaned)
    except ValueError:
        return None


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


def _resolve_host(hostname: str) -> list[str]:
    infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def _validate_resolved_ips(ips: Iterable[str]) -> tuple[bool, list[str], str]:
    resolved = []
    for raw_ip in ips:
        ip = ipaddress.ip_address(raw_ip)
        resolved.append(str(ip))
        if _is_blocked_ip(ip):
            return False, resolved, f"blocked private/internal IP: {ip}"
    return True, resolved, ""


def validate_url(url: str, *, resolve_dns: bool = True) -> UrlSafetyResult:
    """Validate a user-supplied URL before any network request."""
    normalized = normalize_url(url)
    parsed = urlparse(normalized)

    if parsed.scheme not in ALLOWED_SCHEMES:
        return UrlSafetyResult(False, url, normalized, f"invalid URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        return UrlSafetyResult(False, url, normalized, "missing hostname")
    if parsed.username or parsed.password:
        return UrlSafetyResult(False, url, normalized, "URL credentials are not allowed")

    hostname = parsed.hostname.rstrip(".").lower()
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return UrlSafetyResult(False, url, normalized, "hostname is not valid IDNA")

    literal_ip = _host_literal_ip(hostname)
    if literal_ip:
        if _is_blocked_ip(literal_ip):
            return UrlSafetyResult(
                False,
                url,
                normalized,
                f"blocked private/internal IP: {literal_ip}",
                hostname,
                [str(literal_ip)],
            )
        return UrlSafetyResult(True, url, normalized, hostname=hostname, resolved_ips=[str(literal_ip)])

    if not resolve_dns:
        return UrlSafetyResult(True, url, normalized, hostname=hostname)

    try:
        ips = _resolve_host(hostname)
    except socket.gaierror as exc:
        return UrlSafetyResult(False, url, normalized, f"DNS resolution failed: {exc}", hostname)

    ok, resolved, reason = _validate_resolved_ips(ips)
    return UrlSafetyResult(ok, url, normalized, reason, hostname, resolved)


def validate_redirect_chain(urls: Iterable[str]) -> UrlSafetyResult:
    """Validate every URL in a redirect chain to prevent redirect rebinding."""
    last = ""
    for idx, url in enumerate(urls):
        if idx >= _MAX_REDIRECT_VALIDATION_HOPS:
            return UrlSafetyResult(False, last, last, "redirect chain exceeds safety limit")
        result = validate_url(url)
        last = result.normalized_url or url
        if not result.ok:
            return result
    return UrlSafetyResult(True, last, last)

