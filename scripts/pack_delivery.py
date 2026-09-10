"""Copy contest deliverables into delivery/ without secrets or node_modules."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "delivery"
DATE = "20260910"


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"copy {src.name} -> {dst} ({dst.stat().st_size} bytes)")


def main() -> None:
    if DEST.exists():
        for child in DEST.iterdir():
            if child.name == "00_README_交付总览.md":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            elif child.is_file() and child.name != "00_README_交付总览.md":
                child.unlink()

    mapping = [
        (ROOT / "docs" / "bp" / f"AlphaQuant-项目申报书-{DATE}.pdf", DEST / "01_申报书" / f"AlphaQuant-项目申报书-{DATE}.pdf"),
        (ROOT / "docs" / "bp" / "AlphaQuant-项目申报书.md", DEST / "01_申报书" / "AlphaQuant-项目申报书.md"),
        (ROOT / "docs" / "pitch" / f"AlphaQuant-路演PPT-{DATE}.pptx", DEST / "02_PPT" / f"AlphaQuant-路演PPT-{DATE}.pptx"),
        (ROOT / "docs" / "pitch" / "路演大纲.md", DEST / "02_PPT" / "路演大纲.md"),
        (ROOT / "docs" / "demo-script.md", DEST / "03_Demo说明" / "demo-script.md"),
        (ROOT / "docs" / "用户手册.md", DEST / "03_Demo说明" / "用户手册.md"),
        (ROOT / "demo.storyboard.json", DEST / "03_Demo说明" / "demo.storyboard.json"),
        (ROOT / "docs" / "demo-video.md", DEST / "03_Demo说明" / "demo-video.md"),
        (ROOT / "docs" / "demo" / "OBS录屏替代方案.md", DEST / "03_Demo说明" / "OBS录屏替代方案.md"),
        (ROOT / "docs" / "用户手册.md", DEST / "05_手册" / "用户手册.md"),
        (ROOT / "docs" / "FAQ.md", DEST / "05_手册" / "FAQ.md"),
        (ROOT / "README.md", DEST / "06_仓库说明" / "README.md"),
        (ROOT / "docs" / "SCOPE.md", DEST / "06_仓库说明" / "SCOPE.md"),
        (ROOT / "docs" / "contest-rules-notes.md", DEST / "06_仓库说明" / "contest-rules-notes.md"),
        (ROOT / "docs" / "冲击冠军计划.md", DEST / "07_冲击冠军计划" / "冲击冠军计划.md"),
    ]
    for src, dst in mapping:
        if not src.exists():
            raise FileNotFoundError(src)
        copy_file(src, dst)

    demo_src = ROOT / "docs" / "demo" / f"AlphaQuant-演示-{DATE}.mp4"
    video_dir = DEST / "04_视频"
    video_dir.mkdir(parents=True, exist_ok=True)
    if demo_src.exists() and demo_src.stat().st_size > 100_000:
        copy_file(demo_src, video_dir / demo_src.name)
    else:
        status = video_dir / "VIDEO_STATUS.md"
        status.write_text(
            "# 演示视频状态\n\n"
            "截至打包时**尚无成片 MP4**（或体积过小）。\n\n"
            "- 分镜：`../03_Demo说明/demo.storyboard.json`\n"
            "- 按钮脚本：`../03_Demo说明/demo-script.md`\n"
            "- OBS 方案：`../03_Demo说明/OBS录屏替代方案.md`\n"
            "- 自动流水线：仓库根目录 `scripts/run-demo-video.ps1`\n",
            encoding="utf-8",
        )
        print(f"wrote {status}")

    url = DEST / "03_Demo说明" / "DEMO_URL_待填.txt"
    url.write_text(
        "公网 Demo URL：______________________________\n"
        "（本轮未部署魔搭创空间，避免消耗 Token。）\n"
        "本地：http://localhost:3000\n"
        "后端健康检查：http://127.0.0.1:8010/health\n"
        "OpenAPI：http://127.0.0.1:8010/docs\n"
        "启动：仓库根目录 .\\scripts\\dev.ps1\n",
        encoding="utf-8",
    )
    print(f"wrote {url}")

    local = DEST / "03_Demo说明" / "本地演示说明.md"
    local.write_text(
        "# AlphaQuant 本地演示说明\n\n"
        "无需登录、无测试账号。\n\n"
        "```powershell\n"
        "cd <仓库根目录>\n"
        ".\\scripts\\dev.ps1\n"
        "```\n\n"
        "浏览器打开 **http://localhost:3000**。左下角数据源选 **离线演示（可断网）**。\n\n"
        "主路径：仪表盘 **一键演示案例 1** → 选股 **刷新选股** → 回测 **运行回测** → "
        "组合 **优化入选篮子** / **加载 Brinson 归因** → 风控 **评估风险平价组合** → "
        "适当性 **填入保守示例** / **提交问卷并匹配** → 案例2 **运行案例 2 批量回测**。\n\n"
        "离线样本内（2026-09-10）：风险平价夏普 **0.20** vs 等权 **-0.07**，样本内模拟，不是收益承诺。\n\n"
        "公网链接见同目录 `DEMO_URL_待填.txt`。\n",
        encoding="utf-8",
    )
    print(f"wrote {local}")
    print("PACK_OK")


if __name__ == "__main__":
    main()
