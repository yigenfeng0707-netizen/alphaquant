"""Dump offline demo KPIs for PPT/PDF copy. Run from anywhere."""
from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8010"


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    c1 = get("/api/case1?source=offline")
    d = c1["data"]
    b = get("/api/attribution/brinson?source=offline")
    bd = b["data"]
    c2 = get("/api/case2?source=offline")
    d2 = c2["data"]
    out = {
        "data_source": c1.get("data_source"),
        "sharpe_rp": d["sharpe_rp"],
        "sharpe_eq": d["sharpe_eq"],
        "sharpe_rp_ui": f"{d['sharpe_rp']:.2f}",
        "sharpe_eq_ui": f"{d['sharpe_eq']:.2f}",
        "better": d["sharpe_rp_better"],
        "var95_pct": round(d["risk"]["var_cvar"]["d1_95"]["var"] * 100, 2),
        "cvar95_pct": round(d["risk"]["var_cvar"]["d1_95"]["cvar"] * 100, 2),
        "rp_end": round(d["notional"]["rp_end_value"]),
        "eq_end": round(d["notional"]["eq_end_value"]),
        "factor_count": d.get("factor_count"),
        "picks": [f"{p['code']} {p['name']}" for p in d.get("picks") or []],
        "brinson_alloc_pct": round(bd["allocation"] * 100, 2),
        "brinson_sel_pct": round(bd["selection"] * 100, 2),
        "brinson_inter_pct": round(bd.get("interaction", 0) * 100, 2),
        "brinson_excess_pct": round(bd["excess_return"] * 100, 2),
        "case2_notional": d2.get("notional"),
        "case2_var95": (d2.get("report") or {}).get("var_cvar", {}).get("d1_95", {}).get("var"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
