import pytest

from app.services.media import MediaError, parse_timestamp
from app.services.urls import UrlError, is_platform_url, is_public_ip, resolve_target


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/video.mp4",
    "http://localhost/video.mp4",
    "http://169.254.169.254/latest/meta-data/",      # cloud metadata
    "http://10.0.0.5/cam.mp4",
    "http://192.168.1.10/cam.mp4",
    "http://[::1]/v.mp4",
    "http://[::ffff:127.0.0.1]/v.mp4",               # IPv4-mapped loopback
    "http://100.64.0.1/v.mp4",                       # CGNAT
    "http://0.0.0.0/v.mp4",
    "file:///etc/passwd",
    "ftp://example.com/v.mp4",
    "http://user:pass@example.com/v.mp4",
    "http://example.com:22/v.mp4",
    "not a url",
])
def test_rejects_unsafe_urls(url):
    with pytest.raises(UrlError):
        resolve_target(url)


def test_public_ip_rules():
    assert is_public_ip("8.8.8.8")
    assert not is_public_ip("172.16.0.1")
    assert not is_public_ip("fd00::1")
    assert not is_public_ip("::ffff:10.0.0.1")


def test_platform_detection():
    assert is_platform_url("https://www.youtube.com/watch?v=abc")
    assert is_platform_url("https://youtu.be/abc")
    assert not is_platform_url("https://youtube.com.evil.example/x.mp4")


@pytest.mark.parametrize("value,expected", [("225", 225), ("3:45", 225), ("1:20:45", 4845), ("2.5", 2.5),
                                            (None, None), ("", None)])
def test_parse_timestamp(value, expected):
    assert parse_timestamp(value) == expected


@pytest.mark.parametrize("value", ["abc", "1:2:3:4", "-5", "5s"])
def test_parse_timestamp_rejects(value):
    with pytest.raises(MediaError):
        parse_timestamp(value)
