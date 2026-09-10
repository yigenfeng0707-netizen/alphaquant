"""AlphaQuant 1080p title cards for demo video (avoid engine default brand)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "demo"
W, H = 1920, 1080
NAVY = (11, 18, 32)
GOLD = (201, 162, 39)
CREAM = (245, 239, 224)
MUTED = (154, 171, 196)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False):
    path = Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc")
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def card(title: str, subtitle: str, extra: str, out: Path) -> None:
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 12], fill=GOLD)
    d.rectangle([0, H - 12, W, H], fill=GOLD)
    d.rectangle([0, 0, 12, H], fill=GOLD)
    d.text((80, 72), "ALPHAQUANT", fill=GOLD, font=font(28, True))
    d.text((80, 118), "2026 上海（长三角）中青年工程师创新创业大赛 · 金融科技", fill=MUTED, font=font(22))
    bbox = d.textbbox((0, 0), title, font=font(84, True))
    d.text(((W - (bbox[2] - bbox[0])) // 2, 380), title, fill=WHITE, font=font(84, True))
    bbox2 = d.textbbox((0, 0), subtitle, font=font(32))
    d.text(((W - (bbox2[2] - bbox2[0])) // 2, 500), subtitle, fill=CREAM, font=font(32))
    bbox3 = d.textbbox((0, 0), extra, font=font(24))
    d.text(((W - (bbox3[2] - bbox3[0])) // 2, 900), extra, fill=MUTED, font=font(24))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"wrote {out} {out.stat().st_size}")


def kpi_still(out: Path) -> None:
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 12], fill=GOLD)
    d.text((80, 60), "案例 1 · 离线样本内（不是收益承诺）", fill=GOLD, font=font(36, True))
    cells = [
        (80, 180, "风险平价夏普", "0.20"),
        (500, 180, "等权夏普", "-0.07"),
        (920, 180, "日度 95% VaR", "1.40%"),
        (1340, 180, "平价是否更优", "是"),
        (80, 480, "配置效应", "4.65%"),
        (500, 480, "选择效应", "3.16%"),
        (920, 480, "超额", "6.15%"),
        (1340, 480, "因子数", "12"),
    ]
    for x, y, lab, val in cells:
        d.rounded_rectangle([x, y, x + 380, y + 220], radius=16, fill=(20, 30, 50), outline=GOLD, width=2)
        d.text((x + 24, y + 28), lab, fill=MUTED, font=font(22))
        d.text((x + 24, y + 90), val, fill=CREAM, font=font(48, True))
    d.text(
        (80, 980),
        "数据源 offline_synthetic_demo · 仪表盘「一键演示案例 1」· 1 亿为案例2名义本金",
        fill=MUTED,
        font=font(22),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"wrote {out} {out.stat().st_size}")


if __name__ == "__main__":
    card(
        "AlphaQuant",
        "因子增强选股 · 风险平价配置（演示，非实盘）",
        "未接入大模型  ·  回测不等于承诺",
        OUT / "intro-card.png",
    )
    card(
        "谢谢",
        "AlphaQuant · 演示非实盘 · 回测不等于承诺",
        "本地 http://localhost:3000  ·  断网可用离线样本",
        OUT / "outro-card.png",
    )
    kpi_still(OUT / "kpi-still.png")
