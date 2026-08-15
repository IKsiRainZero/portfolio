# brand-spec.md · Portfolio Landing

> 设计方向：**A+B 融合**（理性信息架构 × 安静编辑主义）
> 参考系：Pentagram/Tufte/Vignelli（信息架构）× Kenya Hara/Dieter Rams（编辑极简）
> 决策日期：2026-08-14 · v0 草稿：docs/index.html（待用户确认后进 v1）

## 设计系统

- **色彩**（≤4 色 + 灰度派生）：
  - 纸白 `#F7F5F0`（底）· 纸深 `#EFECE4`（hover 层）
  - 墨黑 `#1A1A1A`（文字）· 墨软 `#55534D` · 墨淡 `#8B887F`（灰度派生，非新色相）
  - 强调 深青 `#0E7C86`（链接/编号/激活态，唯一彩色）
- **字体**（3 族，记录决策：mono 仅用于数据/标签区）：
  - 展示/标题：Noto Serif SC（降级 Songti SC/SimSun/Georgia）
  - 正文：system-ui 栈
  - 数据/标签：IBM Plex Mono（降级 Consolas）
- **间距**：8pt 基准（8/16/24/40/64/96）
- **圆角**：≤4px（锐利，理性派）
- **阴影**：无（安静派）；hover 用纸色填充 + 2px 位移
- **动效**：fade-up 入场（≤0.5s，延迟 0.08s 阶梯）；尊重 prefers-reduced-motion

## 签名元素

- 项目状态表（console 式四维行：编号 mono / 名称 serif / 描述 / 技术 mono / 状态标签）
- 数据行（mono）：06 projects / 08 commits / MIT / 634 files
- 一句话 hero（serif 大标题，clamp 40–72px）

## v1 修复清单（自查评审）

1. 移动端 hero 字号对比补足 2.5×（40px/17px → 标题 ≥44px 或正文缩至 15px）
2. 可选：深色模式（prefers-color-scheme）
3. 可选：Tweaks 面板（强调色切换）

## 部署

- 源目录：docs/（GitHub Pages：main 分支 /docs）
- 上线地址：https://iksirainzero.github.io/portfolio/
- 启用方式：仓库 Settings → Pages → Deploy from branch → main + /docs
