from __future__ import annotations
import requests
from typing import Optional, Dict, Any, Tuple

def get_json(url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str,str]] = None, timeout: int = 20) -> Tuple[Optional[dict], Optional[str]]:
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json(), None
    except Exception as e:
        return None, str(e)

def download_file(url: str, dest_path: str, headers: Optional[Dict[str,str]] = None, timeout: int = 60) -> Optional[str]:
    try:
        with requests.get(url, stream=True, headers=headers, timeout=timeout) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return dest_path
    except Exception as e:
        return None
