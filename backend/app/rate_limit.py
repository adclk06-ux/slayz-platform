"""
Shared slowapi Limiter instance, used by main.py (global default limits +
exception handler) and by individual routers that need tighter per-route
limits (e.g. AI assistant chat, article email sharing).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
