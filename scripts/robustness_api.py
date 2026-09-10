"""API negatives: bad query should be 4xx or structured, not a silent 200 lie."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
fails = 0


def request(path: str, method: str = "GET", payload=None):
    url = BASE + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"User-Agent": "AlphaQuant-robust"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return exc.code, body


def check(name: str, ok: bool, detail: str) -> None:
    global fails
    if not ok:
        fails += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def main() -> int:
    s, b = request("/api/screen?top_n=0")
    check("screen top_n=0", s in (400, 422), f"HTTP {s}")
    s, b = request("/health")
    check("health body.ok", s == 200 and b.get("ok") is True, str(b.get("ok")))
    s, b = request("/api/no-such-route")
    check("missing route 404", s == 404, f"HTTP {s}")
    s, b = request("/api/case2?source=offline")
    check(
        "case2 implemented true",
        s == 200 and b.get("implemented") is True and (b.get("data") or {}).get("brinson"),
        f"implemented={b.get('implemented')}",
    )
    s, b = request("/api/suitability/evaluate", "POST", {})
    check("suitability empty body 422", s in (400, 422), f"HTTP {s}")
    s, b = request("/api/suitability/evaluate", "POST", {"answers": {"q1": 3}, "source": "offline"})
    check("suitability incomplete 422", s == 422, f"HTTP {s} detail={b.get('detail')}")
    s, b = request("/api/attribution/brinson?source=offline")
    check(
        "brinson implemented true",
        s == 200 and b.get("implemented") is True and (b.get("data") or {}).get("explain"),
        f"implemented={b.get('implemented')}",
    )
    if fails:
        print("ROBUSTNESS_FAIL")
        return 1
    print("ROBUSTNESS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
