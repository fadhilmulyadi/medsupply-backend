import os
from typing import Optional
from fastapi import Header, HTTPException, status

def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    """
    Jika env API_KEY tidak diset → auth dimatikan (dev mode).
    Set API_KEY di environment untuk mengaktifkan proteksi.
    """
    expected = os.getenv("API_KEY", "").strip()
    if not expected:
        return
    if not x_api_key or x_api_key.strip() != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
