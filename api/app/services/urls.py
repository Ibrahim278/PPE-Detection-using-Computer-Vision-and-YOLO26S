"""Safe fetching of user-supplied video URLs.

A URL field lets anyone make the server send requests, so for direct links:
  * only http/https on ports 80/443, no credentials in the URL;
  * the hostname must resolve only to public IPs (no loopback, private, link-local
    e.g. 169.254.169.254 cloud metadata, CGNAT, multicast, reserved, IPv4-mapped tricks);
  * the connection is made to the IP we validated (Host header + TLS SNI keep
    certificate checks intact), so DNS can't be swapped between check and connect;
  * every redirect is re-validated, at most 5;
  * size is capped by Content-Length and while streaming.
Platform links (YouTube, Vimeo) go through yt-dlp, restricted to those hosts.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

PLATFORM_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "vimeo.com",
                  "www.vimeo.com", "player.vimeo.com"}
ALLOWED_PORTS = {80, 443}
MAX_REDIRECTS = 5
USER_AGENT = "ppe-compliance-api/0.1"


class UrlError(ValueError):
    """Rejected or failed URL (message is safe to show to the user)."""


@dataclass
class Target:
    scheme: str
    host: str
    port: int
    ips: list[str]          # all validated addresses, IPv4 first
    path: str
    query: str


def is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not (addr.is_multicast or addr.is_reserved)


def is_platform_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in PLATFORM_HOSTS


def resolve_target(url: str, allow_private: bool = False) -> Target:
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as e:
        raise UrlError(f"Invalid URL: {e}") from None
    if parts.scheme not in ("http", "https"):
        raise UrlError("Only http:// and https:// links are supported.")
    if parts.username or parts.password:
        raise UrlError("URLs with credentials are not allowed.")
    host = (parts.hostname or "").lower()
    if not host:
        raise UrlError("URL has no host.")
    port = port or (443 if parts.scheme == "https" else 80)
    if port not in ALLOWED_PORTS and not allow_private:
        raise UrlError("Only standard ports (80, 443) are allowed.")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise UrlError(f"Could not resolve host: {host}") from None
    ips = sorted({info[4][0] for info in infos}, key=lambda ip: (":" in ip, ip))
    if not ips:
        raise UrlError(f"Could not resolve host: {host}")
    if not allow_private and not all(is_public_ip(ip) for ip in ips):
        raise UrlError("This address points to a private or internal network and is not allowed.")
    return Target(parts.scheme, host, port, ips, parts.path or "/", parts.query)


def download_direct(url: str, dest: Path, max_bytes: int, timeout: float,
                    allow_private: bool = False) -> Path:
    """Download a direct video link to ``dest`` with SSRF protections."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        t = resolve_target(current, allow_private)
        redirect = None
        last_err: Exception | None = None
        for ip in t.ips:  # only addresses that passed validation; try the next on connect failure
            try:
                redirect = _fetch_pinned(t, ip, current, dest, max_bytes, timeout)
                break
            except httpx.ConnectError as e:
                last_err = e
                continue
            except httpx.HTTPError as e:
                raise UrlError(f"Download failed: {type(e).__name__}") from None
        else:
            raise UrlError(f"Could not connect to {t.host} ({type(last_err).__name__}).")
        if redirect is None:
            return dest
        current = redirect
    raise UrlError("Too many redirects.")


def _fetch_pinned(t: Target, ip: str, current: str, dest: Path, max_bytes: int, timeout: float) -> str | None:
    """GET from a validated IP. Returns a redirect URL, or None when the file was saved."""
    ip_host = f"[{ip}]" if ":" in ip else ip
    default_port = 443 if t.scheme == "https" else 80
    netloc = ip_host if t.port == default_port else f"{ip_host}:{t.port}"
    req_url = urlunsplit((t.scheme, netloc, t.path, t.query, ""))
    host_header = t.host if t.port == default_port else f"{t.host}:{t.port}"
    ext = {"sni_hostname": t.host} if t.scheme == "https" else {}  # TLS cert is checked against t.host
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        with client.stream("GET", req_url, headers={"Host": host_header, "User-Agent": USER_AGENT},
                           extensions=ext) as r:
            if r.status_code in (301, 302, 303, 307, 308):
                loc = r.headers.get("location")
                if not loc:
                    raise UrlError("Redirect without a location.")
                return urljoin(current, loc)
            if r.status_code != 200:
                raise UrlError(f"The server returned HTTP {r.status_code}.")
            ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
            if ctype.startswith(("text/html", "application/json")):
                raise UrlError("That link is a web page, not a video file. Use a direct video link "
                               "or a YouTube/Vimeo link.")
            length = int(r.headers.get("content-length") or 0)
            if length > max_bytes:
                raise UrlError(f"Video is larger than {max_bytes // (1024 * 1024)} MB.")
            size = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(1 << 16):
                    size += len(chunk)
                    if size > max_bytes:
                        raise UrlError(f"Video is larger than {max_bytes // (1024 * 1024)} MB.")
                    f.write(chunk)
    return None


def download_platform(url: str, dest_stem: Path, max_bytes: int, max_seconds: float,
                      start: float | None, end: float | None) -> Path:
    """Download (a section of) a YouTube/Vimeo video with yt-dlp, capped at 720p."""
    try:
        import yt_dlp
        from yt_dlp.utils import download_range_func
    except ImportError:
        raise UrlError("YouTube/Vimeo links need the optional 'yt-dlp' package on the server.") from None

    base = {"quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True, "socket_timeout": 30}
    try:
        with yt_dlp.YoutubeDL(base) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:  # yt-dlp raises many types
        raise UrlError(f"Could not read that video link ({type(e).__name__}).") from None
    duration = float(info.get("duration") or 0)
    s, e_ = start or 0.0, end if end is not None else duration
    if info.get("is_live"):
        raise UrlError("Live streams aren't supported for video jobs; use the Live Monitor.")
    if duration and e_ > duration:
        e_ = duration
    if e_ - s > max_seconds:
        raise UrlError(f"Section is longer than {max_seconds:g} s. Pick a start and end time.")

    opts = {**base, "outtmpl": str(dest_stem) + ".%(ext)s",
            "format": "best[height<=720][ext=mp4]/best[height<=720]/bestvideo[height<=720]",
            "max_filesize": max_bytes}
    if start is not None or end is not None:
        opts["download_ranges"] = download_range_func(None, [(s, e_)])
        opts["force_keyframes_at_cuts"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:
        raise UrlError(f"Download failed ({type(e).__name__}).") from None
    files = sorted(dest_stem.parent.glob(dest_stem.name + ".*"))
    files = [f for f in files if f.suffix not in (".part", ".ytdl")]
    if not files:
        raise UrlError("Download produced no video file.")
    return files[0]
