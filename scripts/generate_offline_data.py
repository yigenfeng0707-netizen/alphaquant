from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "offline"
SEED = 20260909
N_DAYS = 504

UNIVERSE = [
    # code, name, sector, ann_vol, ann_mu, pe, pb, roe, mcap_yi, start_price
    ("D001", "演示银行", "金融", 0.14, 0.095, 5.8, 0.65, 0.12, 1800, 12.0),
    ("D002", "演示保险", "金融", 0.16, 0.090, 8.5, 1.10, 0.11, 900, 18.0),
    ("D003", "演示证券", "金融", 0.22, 0.088, 12.0, 1.40, 0.08, 420, 9.5),
    ("D004", "演示消费", "消费", 0.18, 0.105, 22.0, 5.50, 0.22, 760, 48.0),
    ("D005", "演示医药", "医药", 0.20, 0.100, 28.0, 4.20, 0.15, 510, 36.0),
    ("D006", "演示制造", "制造", 0.19, 0.092, 16.0, 2.10, 0.13, 380, 22.0),
    ("D007", "演示能源", "能源", 0.17, 0.086, 11.0, 1.30, 0.10, 640, 8.4),
    ("D008", "演示电力", "能源", 0.13, 0.082, 14.0, 1.80, 0.09, 520, 21.0),
    ("D009", "演示科技", "科技", 0.38, 0.110, 45.0, 6.80, 0.07, 290, 55.0),
    ("D010", "演示传媒", "可选", 0.42, 0.108, 38.0, 3.90, 0.05, 120, 7.2),
    ("D011", "演示新能源", "制造", 0.45, 0.112, 52.0, 4.50, 0.04, 210, 31.0),
    ("D012", "演示军工", "制造", 0.40, 0.100, 48.0, 3.20, 0.06, 160, 14.5),
]


def generate() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    dates = pd.bdate_range("2024-01-02", periods=N_DAYS)
    n = len(UNIVERSE)
    vols = np.array([u[3] for u in UNIVERSE])
    mus = np.array([u[4] for u in UNIVERSE])
    daily_mu = mus / 252.0
    daily_vol = vols / np.sqrt(252.0)

    market = rng.normal(0.08 / 252.0, 0.16 / np.sqrt(252.0), size=N_DAYS)
    # 样本中段嵌入一段极端下跌，供压力测试展示
    crash = slice(210, 225)
    market[crash] -= 0.018

    beta = 0.55 + 0.9 * (vols - vols.min()) / (vols.max() - vols.min())
    idio_vol = np.sqrt(np.clip(daily_vol**2 - (beta * 0.16 / np.sqrt(252.0)) ** 2, 1e-8, None))

    rets = np.zeros((N_DAYS, n))
    past_mom = np.zeros(n)
    for t in range(N_DAYS):
        mom_coef = 0.12 if t < N_DAYS // 2 else -0.03  # 后半段动量衰减
        shock = beta * market[t] + rng.normal(0.0, 1.0, size=n) * idio_vol
        rets[t] = daily_mu + shock + mom_coef * past_mom / 252.0
        if t >= 20:
            past_mom = rets[t - 20 : t].sum(axis=0)
        past_mom = np.clip(past_mom, -0.4, 0.4)

    closes = np.zeros((N_DAYS, n))
    closes[0] = np.array([u[9] for u in UNIVERSE])
    for t in range(1, N_DAYS):
        closes[t] = closes[t - 1] * (1.0 + rets[t])

    rows = []
    for j, u in enumerate(UNIVERSE):
        code, name = u[0], u[1]
        px = closes[:, j]
        for t, dt in enumerate(dates):
            rt = float(rets[t, j])
            o = px[t] / (1.0 + rt * 0.4) if t else px[t]
            hi = max(o, px[t]) * (1.0 + abs(rt) * 0.6 + 0.002)
            lo = min(o, px[t]) * (1.0 - abs(rt) * 0.6 - 0.002)
            vol = float(rng.lognormal(mean=15.2 - 0.8 * np.log(u[3] / 0.2), sigma=0.35))
            rows.append(
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "code": code,
                    "name": name,
                    "open": round(float(o), 4),
                    "high": round(float(hi), 4),
                    "low": round(float(lo), 4),
                    "close": round(float(px[t]), 4),
                    "volume": int(vol),
                }
            )

    prices = pd.DataFrame(rows)
    universe = pd.DataFrame(
        [
            {
                "code": u[0],
                "name": u[1],
                "sector": u[2],
                "pe": u[5],
                "pb": u[6],
                "roe": u[7],
                "mcap": u[8] * 1e8,
            }
            for u in UNIVERSE
        ]
    )
    prices.to_csv(OUT / "prices.csv", index=False, encoding="utf-8")
    universe.to_csv(OUT / "universe.csv", index=False, encoding="utf-8")
    meta = {
        "kind": "offline_synthetic_demo",
        "seed": SEED,
        "n_days": N_DAYS,
        "n_names": n,
        "start": dates[0].strftime("%Y-%m-%d"),
        "end": dates[-1].strftime("%Y-%m-%d"),
        "note": "合成演示面板：低波动资产夏普更高，用于展示风险平价相对等权的风险调整优势；后半段动量溢价衰减。不是实盘。",
        "crash_window": [dates[210].strftime("%Y-%m-%d"), dates[224].strftime("%Y-%m-%d")],
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text(
        "# 离线演示数据\n\n本目录为 **合成样本**，仅用于断网演示与算法复现。\n\n"
        "- 不是交易所行情，不能称为实盘。\n"
        "- 股票名称带「演示」前缀，代码为 D001–D012。\n"
        f"- 生成种子 `{SEED}`，约 {N_DAYS} 个交易日。\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} prices={len(prices)} universe={len(universe)}")


if __name__ == "__main__":
    generate()
