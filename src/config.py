FAKE_HANDY_HOST = "127.0.0.1"
FAKE_HANDY_PORT = 5000
FAPTAP_URL = "https://faptap.net"
THEEDGY_URL = "https://theedgy.app"
RESTIM_WS_URL = "ws://127.0.0.1:12346/tcode"

# Network reverse-proxy mode (LAN clients open http://<host-ip>:NETWORK_PROXY_PORT)
NETWORK_PROXY_HOST = "0.0.0.0"
NETWORK_PROXY_PORT = 8080

# Sites that the reverse proxy can target. The Handy API impersonation works
# the same for all of them — only the upstream HTML/CDN host differs.
NETWORK_TARGETS = {
    "faptap": "https://faptap.net",
    "sexlikereal": "https://www.sexlikereal.com",
}
NETWORK_TARGET_LABELS = {
    "faptap": "FapTap",
    "sexlikereal": "SexLikeReal",
}
DEFAULT_NETWORK_TARGET = "faptap"

SITES = {
    "faptap": FAPTAP_URL,
    "theedgy": THEEDGY_URL,
    # Special "site": when active, the embedded browser shows an info page
    # and the reverse proxy serves FapTap to LAN clients.
    "network": "about:blank",
}

HANDY_API_BASES = [
    "https://www.handyfeeling.com/api/handy/v2",
    "https://www.handyfeeling.com/api/handy-rest/v2",
    "https://staging.handyfeeling.com/api/handy/v2",
]
