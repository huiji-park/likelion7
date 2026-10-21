"""KOSIS OpenAPI client: list / meta / data, with cache, retry, key masking.

Key handling: KOSIS_API_KEY env var; fallback load_dotenv(KOSIS_ENV_PATH or DEFAULT_ENV).
The key is never logged, never part of the cache filename/key.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE = "https://kosis.kr/openapi"
DEFAULT_ENV = r"C:\Users\USER\Documents\NLP\likelion7\.env"
ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "cache"

# KOSIS error codes that retrying cannot fix (param / auth / no data)
NON_RETRY = {"10", "11", "12", "20", "21", "30", "31", "41", "42", "50", "60", "61"}


class KosisError(Exception):
    def __init__(self, err, msg):
        super().__init__(f"{err}: {msg}")
        self.err, self.msg = str(err), msg


def get_key() -> str:
    if not os.getenv("KOSIS_API_KEY"):
        load_dotenv(os.getenv("KOSIS_ENV_PATH", DEFAULT_ENV))
    key = os.getenv("KOSIS_API_KEY")
    if not key:
        raise RuntimeError("KOSIS_API_KEY not set")
    return key


def mask(text) -> str:
    text = re.sub(r"(apiKey=)[^&\s\"']+", r"\1***", str(text), flags=re.I)
    k = os.getenv("KOSIS_API_KEY")
    if k:
        text = text.replace(k, "***")
    return text


def _parse(txt: str):
    txt = txt.strip().lstrip("\ufeff")
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        # KOSIS sometimes returns non-strict JSON (unquoted keys)
        return json.loads(re.sub(r'([{,]\s*)([A-Za-z_]\w*)\s*:', r'\1"\2":', txt))


def _decode(b: bytes) -> str:
    for enc in ("utf-8", "cp949"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "replace")


class Kosis:
    def __init__(self, delay=0.4, retries=4, timeout=40, cache_dir=CACHE_DIR):
        self.key = get_key()
        self.delay, self.retries, self.timeout = delay, retries, timeout
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.s = requests.Session()
        self._last = 0.0

    def _cache_path(self, path, params):
        h = hashlib.sha1(json.dumps([path, sorted(params.items())], ensure_ascii=False).encode()).hexdigest()
        return self.cache_dir / f"{path.replace('/', '_').replace('.do', '')}_{h}.json"

    def call(self, path: str, params: dict, use_cache=True):
        params = {**params, "format": "json", "jsonVD": "Y"}
        cp = self._cache_path(path, params)  # apiKey not included
        if use_cache and cp.exists():
            return json.loads(cp.read_text(encoding="utf-8"))
        url = f"{BASE}/{path}"
        last = None
        i = -1
        for _ in range(self.retries * 3):
            i += 1
            if i >= self.retries:
                break
            wait = self.delay - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            try:
                self._last = time.time()
                r = self.s.get(url, params={**params, "apiKey": self.key}, timeout=self.timeout)
                r.raise_for_status()
                data = _parse(_decode(r.content))
                if isinstance(data, dict) and "err" in data:
                    e = KosisError(data["err"], data.get("errMsg"))
                    if e.err in NON_RETRY:
                        raise e
                    last = e
                    # err 40 = per-minute call limit (200/min): wait for window reset
                    time.sleep(62 if e.err == "40" else 2 ** i)
                    if e.err == "40":
                        i = 0
                    continue
                cp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return data
            except KosisError:
                raise
            except Exception as e:  # network / parse
                last = Exception(mask(e))
                time.sleep(2 ** i)
        raise last

    # ---- endpoints ----
    def list(self, vwCd, parentListId):
        return self.call("statisticsList.do", {"method": "getList", "vwCd": vwCd, "parentListId": parentListId})

    def meta(self, orgId, tblId, type_):
        return self.call("statisticsData.do", {"method": "getMeta", "type": type_, "orgId": orgId, "tblId": tblId})

    def data(self, **kw):
        return self.call("Param/statisticsParameterData.do", {"method": "getList", **kw})
