# AlphaQuant 演示视频

## 自动流水线（优先）

前置：后端 `8010`、前端 `http://localhost:3000` 已启动；`frontend` 已 `npm i -D playwright`；本机有 ffmpeg、edge-tts。

```powershell
cd <仓库根>
python .\scripts\render_demo_stills.py
powershell -File .\scripts\run-demo-video.ps1
```

成片默认：`demo-output/AlphaQuant_demo_cinematic_3min.mp4`  
带日期副本：`docs/demo/AlphaQuant-演示-20260910.mp4`

分镜：根目录 `demo.storyboard.json`（按钮 `data-testid` 与 2026-09-10 UI 一致）。片头片尾用 `assets/demo/*.png`，避免引擎默认他品标题卡。

## 人工 OBS 方案

见 `docs/demo/OBS录屏替代方案.md`。流水线失败时不要假装已有成片。
