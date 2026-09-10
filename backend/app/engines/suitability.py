"""Investment suitability questionnaire, matching, local audit log.

Demo-only: no real ID numbers, no KYC documents.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import AUDIT_DIR
from app.utils import json_safe

PROFILES = (
    ("conservative", "保守", 8, 14),
    ("steady", "稳健", 15, 20),
    ("balanced", "平衡", 21, 26),
    ("active", "积极", 27, 32),
    ("aggressive", "进取", 33, 40),
)

# 与风险平价 / 仓位 / 波动挂钩的演示规则（非监管报备、非投顾建议）
PROFILE_RULES: dict[str, dict[str, Any]] = {
    "conservative": {
        "allowed_methods": ["min_variance"],
        "preferred_method": "min_variance",
        "max_ann_vol": 0.16,
        "max_abs_dd": 0.18,
        "max_single_weight": 0.18,
        "max_equity_weight": 0.55,
        "note": "优先最小方差，股票仓位上限 55%，其余视为现金缓冲。",
    },
    "steady": {
        "allowed_methods": ["min_variance", "risk_parity"],
        "preferred_method": "risk_parity",
        "max_ann_vol": 0.22,
        "max_abs_dd": 0.25,
        "max_single_weight": 0.22,
        "max_equity_weight": 1.0,
        "note": "允许风险平价；默认演示满仓可通过，仍检查波动与单票上限。",
    },
    "balanced": {
        "allowed_methods": ["min_variance", "risk_parity", "equal_weight"],
        "preferred_method": "risk_parity",
        "max_ann_vol": 0.28,
        "max_abs_dd": 0.32,
        "max_single_weight": 0.28,
        "max_equity_weight": 1.0,
        "note": "风险平价为默认匹配产品。",
    },
    "active": {
        "allowed_methods": ["risk_parity", "equal_weight", "max_sharpe"],
        "preferred_method": "risk_parity",
        "max_ann_vol": 0.36,
        "max_abs_dd": 0.40,
        "max_single_weight": 0.35,
        "max_equity_weight": 1.0,
        "note": "允许最大夏普，但仍检查波动与单票上限。",
    },
    "aggressive": {
        "allowed_methods": ["min_variance", "risk_parity", "equal_weight", "max_sharpe"],
        "preferred_method": "max_sharpe",
        "max_ann_vol": 0.55,
        "max_abs_dd": 0.55,
        "max_single_weight": 0.40,
        "max_equity_weight": 1.0,
        "note": "演示档最高风险偏好，仍禁止把回测当承诺。",
    },
}

QUESTIONS = [
    {
        "id": "q1",
        "title": "计划投资期限",
        "options": [
            {"value": 1, "label": "1 年以内"},
            {"value": 2, "label": "1–3 年"},
            {"value": 3, "label": "3–5 年"},
            {"value": 4, "label": "5–10 年"},
            {"value": 5, "label": "10 年以上"},
        ],
    },
    {
        "id": "q2",
        "title": "未来三年收入稳定性",
        "options": [
            {"value": 1, "label": "很不稳定"},
            {"value": 2, "label": "不太稳定"},
            {"value": 3, "label": "一般"},
            {"value": 4, "label": "较稳定"},
            {"value": 5, "label": "非常稳定"},
        ],
    },
    {
        "id": "q3",
        "title": "股票/基金投资经验",
        "options": [
            {"value": 1, "label": "无经验"},
            {"value": 2, "label": "1 年以内"},
            {"value": 3, "label": "1–3 年"},
            {"value": 4, "label": "3–5 年"},
            {"value": 5, "label": "5 年以上"},
        ],
    },
    {
        "id": "q4",
        "title": "可接受的最大回撤（演示分档）",
        "options": [
            {"value": 1, "label": "约 5%"},
            {"value": 2, "label": "约 10%"},
            {"value": 3, "label": "约 20%"},
            {"value": 4, "label": "约 30%"},
            {"value": 5, "label": "40% 以上"},
        ],
    },
    {
        "id": "q5",
        "title": "若组合一个月下跌约 15%，您更可能",
        "options": [
            {"value": 1, "label": "全部赎回"},
            {"value": 2, "label": "明显减仓"},
            {"value": 3, "label": "继续持有"},
            {"value": 4, "label": "小幅加仓"},
            {"value": 5, "label": "显著加仓"},
        ],
    },
    {
        "id": "q6",
        "title": "本笔资金占可投资产比例",
        "options": [
            {"value": 1, "label": "超过 70%"},
            {"value": 2, "label": "50–70%"},
            {"value": 3, "label": "30–50%"},
            {"value": 4, "label": "10–30%"},
            {"value": 5, "label": "低于 10%"},
        ],
    },
    {
        "id": "q7",
        "title": "对波动、回撤、风险平价等概念的了解",
        "options": [
            {"value": 1, "label": "几乎不了解"},
            {"value": 2, "label": "听说过"},
            {"value": 3, "label": "能看懂指标"},
            {"value": 4, "label": "能独立比较策略"},
            {"value": 5, "label": "能解释风险贡献"},
        ],
    },
    {
        "id": "q8",
        "title": "更接近的投资目标",
        "options": [
            {"value": 1, "label": "尽量保本"},
            {"value": 2, "label": "稳健增值"},
            {"value": 3, "label": "平衡收益与回撤"},
            {"value": 4, "label": "追求较高收益"},
            {"value": 5, "label": "接受高波动换弹性"},
        ],
    },
]

PRESETS = {
    "conservative": {"q1": 1, "q2": 2, "q3": 1, "q4": 1, "q5": 1, "q6": 1, "q7": 2, "q8": 1},
    "steady": {"q1": 2, "q2": 3, "q3": 2, "q4": 2, "q5": 2, "q6": 2, "q7": 3, "q8": 2},
    "balanced": {"q1": 3, "q2": 3, "q3": 3, "q4": 3, "q5": 3, "q6": 3, "q7": 3, "q8": 3},
    "active": {"q1": 4, "q2": 4, "q3": 4, "q4": 4, "q5": 4, "q6": 4, "q7": 4, "q8": 4},
    "aggressive": {"q1": 5, "q2": 5, "q3": 5, "q4": 5, "q5": 5, "q6": 5, "q7": 5, "q8": 5},
}

METHOD_LABELS = {
    "equal_weight": "等权",
    "risk_parity": "风险平价",
    "min_variance": "最小方差",
    "max_sharpe": "最大夏普",
}


def questionnaire() -> dict:
    return {
        "title": "投资适当性风险评估（演示）",
        "disclaimer": "本地演示问卷，不采集身份证号，不构成正式合格投资者认定或投资建议。",
        "questions": QUESTIONS,
        "profiles": [
            {
                "id": pid,
                "label": label,
                "score_min": lo,
                "score_max": hi,
                **{k: v for k, v in PROFILE_RULES[pid].items() if k != "allowed_methods"},
                "allowed_methods": PROFILE_RULES[pid]["allowed_methods"],
            }
            for pid, label, lo, hi in PROFILES
        ],
        "presets": {k: {"label": PROFILE_RULES[k]["note"], "answers": v} for k, v in PRESETS.items()},
    }


def score_answers(answers: dict[str, int]) -> dict:
    qids = [q["id"] for q in QUESTIONS]
    missing = [qid for qid in qids if qid not in answers]
    if missing:
        raise ValueError(f"缺少题目答案: {','.join(missing)}")
    total = 0
    cleaned: dict[str, int] = {}
    for qid in qids:
        v = int(answers[qid])
        if v < 1 or v > 5:
            raise ValueError(f"{qid} 分值须为 1–5")
        cleaned[qid] = v
        total += v
    profile_id, label = "balanced", "平衡"
    for pid, plabel, lo, hi in PROFILES:
        if lo <= total <= hi:
            profile_id, label = pid, plabel
            break
    if total < PROFILES[0][2]:
        profile_id, label = PROFILES[0][0], PROFILES[0][1]
    if total > PROFILES[-1][3]:
        profile_id, label = PROFILES[-1][0], PROFILES[-1][1]
    return {"score": total, "profile_id": profile_id, "profile_label": label, "answers": cleaned}


def answers_summary(answers: dict[str, int]) -> str:
    by_id = {q["id"]: q for q in QUESTIONS}
    parts = []
    for qid, val in answers.items():
        q = by_id.get(qid)
        if not q:
            continue
        opt = next((o for o in q["options"] if o["value"] == val), None)
        parts.append(f"{q['title']}={opt['label'] if opt else val}")
    return "；".join(parts)


def _max_weight(weights: list[dict]) -> float:
    if not weights:
        return 0.0
    return float(max(abs(float(r.get("weight") or 0.0)) for r in weights))


def match_portfolio(profile_id: str, method: str, metrics: dict, weights: list[dict], equity_weight: float = 1.0) -> dict:
    rules = PROFILE_RULES.get(profile_id) or PROFILE_RULES["balanced"]
    method = method if method in METHOD_LABELS else "risk_parity"
    vol = float(metrics.get("volatility") or 0.0)
    dd = abs(float(metrics.get("max_drawdown") or 0.0))
    mxw = _max_weight(weights)
    reasons: list[str] = []
    hard: list[str] = []
    warns: list[str] = []

    if method not in rules["allowed_methods"]:
        hard.append(
            f"组合方法「{METHOD_LABELS.get(method, method)}」不在「{next(p[1] for p in PROFILES if p[0]==profile_id)}」允许列表"
            f"（允许：{' / '.join(METHOD_LABELS[m] for m in rules['allowed_methods'])}）"
        )
    if vol > rules["max_ann_vol"] + 1e-12:
        hard.append(f"样本内年化波动 {vol:.2%} 超过档位上限 {rules['max_ann_vol']:.0%}")
    elif vol > rules["max_ann_vol"] * 0.9:
        warns.append(f"样本内年化波动 {vol:.2%} 接近上限 {rules['max_ann_vol']:.0%}")
    if dd > rules["max_abs_dd"] + 1e-12:
        hard.append(f"样本内最大回撤 {dd:.2%} 超过档位上限 {rules['max_abs_dd']:.0%}")
    elif dd > rules["max_abs_dd"] * 0.9:
        warns.append(f"样本内最大回撤 {dd:.2%} 接近上限 {rules['max_abs_dd']:.0%}")
    if mxw > rules["max_single_weight"] + 1e-12:
        hard.append(f"单票权重 {mxw:.2%} 超过上限 {rules['max_single_weight']:.0%}（与风险贡献集中度相关）")
    if equity_weight > rules["max_equity_weight"] + 1e-12:
        if rules["max_equity_weight"] < 0.99:
            hard.append(
                f"当前演示组合股票仓位 {equity_weight:.0%} 超过该档上限 {rules['max_equity_weight']:.0%}，"
                f"建议现金缓冲 {1.0 - rules['max_equity_weight']:.0%}"
            )
        else:
            warns.append("满仓演示组合，请确认流动性安排")
    elif equity_weight > rules["max_equity_weight"] * 0.95 and rules["max_equity_weight"] < 0.99:
        warns.append(f"股票仓位 {equity_weight:.0%} 接近上限 {rules['max_equity_weight']:.0%}")

    if hard:
        decision = "拦截"
    elif warns:
        decision = "警告"
    else:
        decision = "通过"
    suggested = method if decision != "拦截" else rules["preferred_method"]
    if method not in rules["allowed_methods"]:
        suggested = rules["preferred_method"]
    reasons = hard + warns
    if not reasons:
        reasons.append(
            f"方法 {METHOD_LABELS[method]} 的波动/回撤/单票权重落在「{next(p[1] for p in PROFILES if p[0]==profile_id)}」规则内"
        )
    return json_safe(
        {
            "decision": decision,
            "ok": decision != "拦截",
            "blocked": decision == "拦截",
            "method": method,
            "method_label": METHOD_LABELS.get(method, method),
            "suggested_method": suggested,
            "suggested_method_label": METHOD_LABELS.get(suggested, suggested),
            "checks": {
                "volatility": vol,
                "max_drawdown": dd,
                "max_single_weight": mxw,
                "equity_weight": equity_weight,
                "limits": {
                    "max_ann_vol": rules["max_ann_vol"],
                    "max_abs_dd": rules["max_abs_dd"],
                    "max_single_weight": rules["max_single_weight"],
                    "max_equity_weight": rules["max_equity_weight"],
                    "allowed_methods": rules["allowed_methods"],
                },
            },
            "reasons": reasons,
            "rule_note": rules["note"],
        }
    )


def audit_path() -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    return AUDIT_DIR / "suitability.jsonl"


def append_audit(record: dict) -> str:
    path = audit_path()
    line = json.dumps(json_safe(record), ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    return str(path)


def read_audit(limit: int = 20) -> list[dict]:
    path = audit_path()
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.reverse()
    return rows


def build_audit_record(
    *,
    scored: dict,
    match: dict,
    session_label: str,
    data_source: str,
    method: str,
) -> dict:
    label = (session_label or "本地演示").strip()[:32] or "本地演示"
    if any(tok in label for tok in ("身份证", "身份证号", "idcard")):
        label = "本地演示"
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "session_label": label,
        "score": scored["score"],
        "profile_id": scored["profile_id"],
        "profile_label": scored["profile_label"],
        "answers_summary": answers_summary(scored["answers"]),
        "method": method,
        "decision": match["decision"],
        "blocked": match["blocked"],
        "suggested_method": match.get("suggested_method"),
        "data_source": data_source,
        "note": "演示审计日志，不含证件号。",
    }
