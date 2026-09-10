"""HTTP smoke: health + case1 + P1 suitability/brinson/case2. Exit non-zero on FAIL."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
fails = 0


def get(path: str) -> dict:
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": "AlphaQuant-smoke"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read().decode("utf-8")
        body = json.loads(raw)
        return {"status": resp.status, "body": body}


def post(path: str, payload: dict) -> dict:
    url = BASE + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "AlphaQuant-smoke", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return {"status": resp.status, "body": body}


def check(name: str, ok: bool, msg: str) -> None:
    global fails
    tag = "PASS" if ok else "FAIL"
    if not ok:
        fails += 1
    print(f"[{tag}] {name} {msg}")


def main() -> int:
    try:
        got = get("/health")
        check("health", got["status"] == 200 and got["body"].get("ok") is True, f"ok={got['body'].get('ok')}")
    except Exception as exc:
        check("health", False, str(exc))

    try:
        got = get("/api/case1?source=offline")
        b = got["body"]
        d = b.get("data") or {}
        check(
            "case1",
            got["status"] == 200 and b.get("ok") and d.get("picks") and "sharpe_rp" in d,
            f"source={b.get('data_source')} rp={d.get('sharpe_rp')}",
        )
    except Exception as exc:
        check("case1", False, str(exc))

    for name, path, pred in (
        ("screen", "/api/screen?source=offline", lambda b: (b.get("data") or {}).get("factor_count", 0) >= 10),
        ("backtest", "/api/backtest?source=offline", lambda b: (b.get("data") or {}).get("selected")),
        ("optimize", "/api/optimize?source=offline", lambda b: "risk_parity" in ((b.get("data") or {}).get("methods") or {})),
        ("risk", "/api/risk?source=offline", lambda b: (b.get("data") or {}).get("var_cvar")),
    ):
        try:
            got = get(path)
            check(name, got["status"] == 200 and got["body"].get("ok") and pred(got["body"]), path)
        except Exception as exc:
            check(name, False, str(exc))

    try:
        got = get("/api/suitability?source=offline")
        b = got["body"]
        qs = (b.get("questionnaire") or {}).get("questions") or []
        check(
            "suitability",
            got["status"] == 200 and b.get("implemented") is True and len(qs) >= 6,
            f"implemented={b.get('implemented')} nq={len(qs)}",
        )
    except Exception as exc:
        check("suitability", False, str(exc))

    try:
        got = post(
            "/api/suitability/evaluate",
            {
                "answers": {"q1": 3, "q2": 3, "q3": 3, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 3},
                "source": "offline",
                "method": "risk_parity",
                "session_label": "本地演示",
            },
        )
        d = got["body"].get("data") or {}
        match = d.get("match") or {}
        check(
            "suitability-pass",
            got["status"] == 200
            and got["body"].get("implemented") is True
            and d.get("profile_label")
            and match.get("decision")
            and match.get("reasons"),
            f"decision={match.get('decision')} score={d.get('score')}",
        )
    except Exception as exc:
        check("suitability-pass", False, str(exc))

    try:
        got = post(
            "/api/suitability/evaluate",
            {
                "answers": {"q1": 1, "q2": 2, "q3": 1, "q4": 1, "q5": 1, "q6": 1, "q7": 2, "q8": 1},
                "source": "offline",
                "method": "risk_parity",
                "session_label": "本地演示",
            },
        )
        d = got["body"].get("data") or {}
        check(
            "suitability-block",
            got["status"] == 200
            and got["body"].get("implemented") is True
            and d.get("match", {}).get("blocked") is True
            and d.get("audit", {}).get("answers_summary"),
            f"decision={d.get('match', {}).get('decision')}",
        )
    except Exception as exc:
        check("suitability-block", False, str(exc))

    try:
        got = get("/api/attribution/brinson?source=offline")
        b = got["body"]
        d = b.get("data") or {}
        check(
            "brinson",
            got["status"] == 200
            and b.get("implemented") is True
            and d.get("allocation") is not None
            and d.get("selection") is not None
            and d.get("explain")
            and d.get("sectors"),
            f"alloc={d.get('allocation')} sel={d.get('selection')} excess={d.get('excess_return')}",
        )
    except Exception as exc:
        check("brinson", False, str(exc))

    try:
        got = get("/api/case2?source=offline")
        b = got["body"]
        d = b.get("data") or {}
        report = d.get("report") or {}
        check(
            "case2",
            got["status"] == 200
            and b.get("implemented") is True
            and (d.get("brinson") or {}).get("allocation") is not None
            and (d.get("scaled") or [])
            and report.get("title")
            and report.get("var_cvar"),
            f"notional={d.get('notional', {}).get('amount')} title={report.get('title')}",
        )
    except Exception as exc:
        check("case2", False, str(exc))

    try:
        got = post("/api/case2/export", {"source": "offline", "fmt": "md", "notional": 100000000})
        d = got["body"].get("data") or {}
        check(
            "case2-export",
            got["status"] == 200 and got["body"].get("implemented") is True and (d.get("export") or {}).get("path"),
            f"file={(d.get('export') or {}).get('filename')}",
        )
    except Exception as exc:
        check("case2-export", False, str(exc))

    if fails:
        print("SMOKE_FAIL")
        return 1
    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
