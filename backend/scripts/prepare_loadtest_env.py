# -*- coding: utf-8 -*-
"""
为 k6 压测准备 TOKEN / BOOK_ID 等环境变量（需 API 已启动且 ENABLE_TEST_USERS=1）。

用法:
  cd backend
  python scripts/prepare_loadtest_env.py --base http://127.0.0.1:8000/api/v2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _json_request(url: str, body: dict | None = None, token: str | None = None, method: str = "POST") -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body or {}).encode("utf-8") if body is not None else None
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000/api/v2")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    a = _json_request(f"{base}/auth/login", {"code": "t", "debug_open_id": "k6_prep_a", "nickname": "k6A"})
    b = _json_request(f"{base}/auth/login", {"code": "t", "debug_open_id": "k6_prep_b", "nickname": "k6B"})
    token_a = a["data"]["token"]
    token_b = b["data"]["token"]
    join_a = a["data"]["user"]["join_code"]

    _json_request(f"{base}/pairs", {"join_code": join_a}, token=token_b)

    book = _json_request(
        f"{base}/books",
        {"title": "k6书", "author": "测", "total_pages": 200},
        token=token_a,
    )
    book_id = book["data"]["book_id"]

    print(f"export TOKEN={token_a}")
    print(f"export TOKEN_A={token_a}")
    print(f"export TOKEN_B={token_b}")
    print(f"export BOOK_ID={book_id}")
    print("export CATALOG_ID=gutendex_1")


if __name__ == "__main__":
    try:
        main()
    except URLError as exc:
        print(f"请求失败: {exc}", file=sys.stderr)
        sys.exit(1)
