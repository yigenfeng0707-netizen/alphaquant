"""Playwright click-through of AlphaQuant pages. Exit non-zero on FAIL."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOT = ROOT / "_tmp_e2e_shots"
FRONT = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[FAIL] playwright python package missing")
        return 2

    SHOT.mkdir(exist_ok=True)
    results = []
    fails = 0

    def rec(name: str, ok: bool, msg: str) -> None:
        nonlocal fails
        if not ok:
            fails += 1
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {msg}")
        results.append({"name": name, "ok": ok, "msg": msg})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(60000)
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))

        def shot(name: str) -> None:
            page.screenshot(path=str(SHOT / f"{name}.png"), full_page=True)

        page.goto(FRONT, wait_until="domcontentloaded")
        page.get_by_test_id("btn-case1").click()
        try:
            page.wait_for_function("() => document.querySelectorAll('.kpi .value').length >= 4", timeout=45000)
            body = page.content()
            rec("dashboard", "案例 1" in body and "风险平价夏普" in body, f"js={js_errors[-2:]}")
        except Exception as exc:
            rec("dashboard", False, str(exc))
        shot("01-dashboard")

        cases = [
            ("screen", "nav-screen", "btn-screen", ["因子增强选股", "股票池评分"]),
            ("backtest", "nav-backtest", "btn-backtest", ["策略回测", "四策略对照"]),
            ("portfolio", "nav-portfolio", "btn-optimize", ["组合优化", "风险平价夏普"]),
            ("risk", "nav-risk", "btn-risk", ["风险监控", "95% VaR"]),
        ]
        for key, nav, btn, needles in cases:
            js_errors.clear()
            page.get_by_test_id(nav).click()
            page.get_by_test_id(btn).click()
            try:
                page.wait_for_selector(".kpi .value", timeout=45000)
                html = page.content()
                ok = all(n in html for n in needles) and not js_errors
                rec(key, ok, f"needles={needles} js={js_errors[:1]}")
            except Exception as exc:
                rec(key, False, str(exc))
            shot(f"02-{key}")

        page.get_by_test_id("nav-suitability").click()
        page.get_by_test_id("btn-preset-conservative").click()
        page.get_by_test_id("btn-suitability-submit").click()
        try:
            page.wait_for_selector(".el-tag", timeout=45000)
            page.wait_for_function("() => document.body.innerText.includes('拦截')", timeout=45000)
            html = page.content()
            rec("suitability", "匹配结果" in html and "拦截" in html, "conservative-block")
        except Exception as exc:
            rec("suitability", False, str(exc))
        shot("03-suitability")

        page.get_by_test_id("nav-case2").click()
        page.get_by_test_id("btn-case2-run").click()
        try:
            page.wait_for_selector("[data-testid='table-case2-batch']", timeout=45000)
            html = page.content()
            rec("case2", "不是已管理" in html and "配置效应" in html, "batch+brinson")
        except Exception as exc:
            rec("case2", False, str(exc))
        shot("04-case2")

        page.get_by_test_id("nav-portfolio").click()
        page.get_by_test_id("btn-brinson").click()
        try:
            page.wait_for_selector("[data-testid='brinson-explain']", timeout=45000)
            txt = page.get_by_test_id("brinson-explain").inner_text()
            rec("portfolio-brinson", len(txt) > 12 and ("配置" in txt or "算术" in txt), txt[:48])
        except Exception as exc:
            rec("portfolio-brinson", False, str(exc))
        shot("05-portfolio-brinson")

        browser.close()

    (SHOT / "browser_accept.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    if fails:
        print("BROWSER_FAIL")
        return 1
    print("BROWSER_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
