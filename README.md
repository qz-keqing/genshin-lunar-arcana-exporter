# 月谕圣牌导出器 · Genshin Lunar Arcana Exporter

一键导出《原神》**「月谕圣牌」收藏**（幻想真境剧诗 · 月谕模式，共 22 张）的小工具：
**米游社 App 扫码登录 → 填 UID → 导出 JSON + 可直接打印成图的自包含 HTML**。

数据来自原神**官方战绩（Battle Chronicle）接口** `role_combat` 中的 `tarot_card_state` 字段：
不抓包、不改包、不读游戏内存，也不收集任何账号密码。

> 本项目与米哈游 / HoYoVerse 无任何关联，为非官方个人工具，仅用于导出**自己账号**的数据。

---

## 功能

* 🔐 **两种登录方式**：米游社 App 扫码（国服，推荐）/ 粘贴 Cookie（国际服或备用）
* 🃏 一键导出 22 张「月谕圣牌」：名称、图标、是否解锁、**重复持有张数（×N，可用于交换）**
* 📊 附带本期统计（难度、圣牌挑战完成数、最高幕数）
* 🖼 生成自包含 HTML（图标已下载到本地），浏览器 `Ctrl+P` 即可打印 / 另存为图片、PDF
* 🧾 同时输出结构化 JSON，方便二次开发
* 🖥 支持命令行与自检模式，便于排错

## 快速开始

### 方式一：直接用打包好的 exe

在 [Releases](https://github.com/qz-keqing/genshin-lunar-arcana-exporter/releases) 下载
`YueYuShengPai-Exporter-v1.0.0.exe`（即「月谕圣牌导出器」，Windows 10/11 64 位，免安装）→ 双击 →

1. **① 扫码登录（国服）**：点「获取二维码」，用**米游社 App** 扫码确认
2. **② 粘贴 Cookie（国际服/备用）**：浏览器登录米游社或 HoYoLAB → `F12` → Network → 复制任一战绩请求的 `Cookie`（至少含 `ltuid_v2`、`ltoken_v2`）
3. 填 UID（可点「列出我的角色」自动填入）→ 点 **一键导出月谕圣牌**

### 方式二：从源码运行

```bash
pip install segno
python src/yysp_gui.py
```

### 方式三：命令行

```bash
python src/export-lunar-arcana.py --cookie "ltuid_v2=...;ltoken_v2=..." --uid 123456789 --server cn_gf01 --out out
# 或： set YYSP_COOKIE=ltuid_v2=...;ltoken_v2=...  &  python src/export-lunar-arcana.py --uid 123456789
```

服务器代码按 UID 首位推断：1–4 `cn_gf01`、5 `cn_qd01`、6 `os_usa`、7 `os_euro`、8 `os_asia`、9 `os_cht`。

## 导出产物

```
out/
  lunar-arcana-<UID>.json      # 22 张牌 + 本期统计 + 接口原始返回
  lunar-arcana-<UID>.html      # 自包含展示页（图标本地化）
  icons-<UID>/card-01.png …    # 圣牌图标
```

## 打包 exe

```powershell
pip install pyinstaller segno
pwsh -File src\build_exe.ps1        # 产物： src\dist\月谕圣牌导出器.exe
```

## 自检 / 测试

```powershell
# 打包后的 exe（无界面，结果写入日志文件）
.\src\dist\月谕圣牌导出器.exe --selftest logs\selftest.txt   # 接口连通 + 扫码通道 + 导出管线
.\src\dist\月谕圣牌导出器.exe --guitest  logs\guitest.txt    # 界面自检

# 源码侧
python tests\selftest_pipeline.py    # 核心流程（离线，伪造接口返回）
python tests\test_gui_smoke.py       # 界面冒烟（需要 segno）
python tests\test_qr_login.py        # 扫码登录通道实测（只创建二维码）
```

## 目录结构

```
src/     yysp_core.py（接口与渲染）· yysp_login.py（扫码登录）· yysp_gui.py（界面）
         export-lunar-arcana.py（命令行）· build_exe.ps1（打包）
docs/    使用说明.md · 接口调研报告.md
tests/   selftest_pipeline.py · test_gui_smoke.py · test_qr_login.py
```

## 关于「UID + 密码登录」

* 官方登录账号是**邮箱 / 手机号**，UID 只是游戏内角色 ID，本身不能用于登录；
* 米哈游密码登录接口带**极验验证码 + 设备风控**，第三方无法合规自动完成——凡是索要账号密码的第三方工具，本质都在**收集你的凭据**；
* 因此本工具只走**扫码**与**Cookie**两条官方通道，全程不接触、不保存、不上传你的密码。

## 免责声明

* 非官方项目，与米哈游 / HoYoVerse 无关；
* 仅供导出**自己账号**的数据，请遵守《原神》用户协议与相关法律法规，不要用于批量抓取或商业用途；
* `role_combat` 属于非公开文档接口，官方随时可能调整；请自行控制请求频率（建议 ≥ 5~10 秒/次）；
* Cookie / 登录态属于敏感凭据，请勿分享给他人，也不要提交到任何仓库。

## 许可

本仓库代码采用 [MIT License](LICENSE)。仓库内不含任何第三方源码或官方前端脚本，参考来源见 [THIRD-PARTY.md](THIRD-PARTY.md)。
