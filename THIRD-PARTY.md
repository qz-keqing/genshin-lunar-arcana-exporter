# 第三方资料与来源说明

本仓库**只包含自行编写的代码与文档**，不收录、不再分发任何第三方源码、官方前端脚本或官方素材。以下是调研过程中参考过的公开资料及其许可，仅以链接形式引用：

| 资料 | 许可 | 本仓库如何使用 |
| --- | --- | --- |
| [UIGF-org/mihoyo-api-collect](https://github.com/UIGF-org/mihoyo-api-collect) | CC-BY-NC 4.0 | 仅用于核对“原神战绩类接口当前只需 Cookie、不再需要 DS 签名”这一鉴权事实；**未复制其文档内容** |
| [seriaati/genshin.py](https://github.com/seriaati/genshin.py) | MIT | 仅用于交叉验证 `role_combat` 返回字段的命名与语义（`tarot_card_state`、`tarot_finished_cnt`、`is_tarot`、`tarot_serial_no`）；**未复制其源码** |
| 米哈游官方战绩页 <https://webstatic.mihoyo.com/app/community-game-records/> 及其国际服版本 | 官方版权所有 | 仅通过浏览器开发者工具核对接口路径与页面路由（`/genshin/api/role_combat`、`/ys/role-combat/tarot`）；**未收录任何官方脚本或图片素材** |
| 官方公告 [Imaginarium Theater Update: Lunar Mode](https://www.hoyolab.com/article/41429066) | 官方版权所有 | 作为“月谕模式/月谕圣牌”机制的出处引用 |

## 游戏素材

工具运行时不会内置任何游戏素材：圣牌图标是导出时从接口返回的图标 URL **临时下载到你本机**的输出目录，仅用于你自己查看收藏。

## 商标

《原神》/ Genshin Impact 及相关名称为米哈游（miHoYo / HoYoverse）的商标或注册商标。本项目为非官方个人工具，与其无任何关联。
