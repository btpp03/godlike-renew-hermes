# 账号 / 服务器信息（Godlike Host 免费档）

> 更新时间：2026-10-26 03:57 UTC / 11:57 北京

## 账号

| 项 | 值 |
| --- | --- |
| 平台 | Godlike Host（免费 Minecraft 服当免费小机器用） |
| 面板 | https://panel.godlike.host （前端 SPA：https://ultra.panel.godlike.host） |
| 官网/购物车 | https://godlike.host/clientarea |
| 登录邮箱 | `nicebtpp@proton.me` |
| 密码 | **不写在这里** —— 仓是 public，这是他惯用密码，明文上去等于全网泄露。见 Actions secret `GODLIKE_PASSWORD` + 本机 `/root/gl/CREDS.txt` |
| clientarea userid | `606551`（面板 `/users/billing` → linked client_id `610060`） |
| 登录接口 | `POST /api/v2/auth/login {"user":email,"password":pw}` → `data.token`（`ptlc_…`） |

## 服务器（当前唯一一台免费服）

| 项 | 值 |
| --- | --- |
| name | `gCL2Bra8_483945` |
| uuid | `ccad3fca-d57b-45fb-bbf8-4eea8a638ca3` |
| 地区 | USA-EAST（location id 23 / 下单 locId **725**） |
| 节点 | node 422 · `srv9007` · wings `wss://wing9007.panel.godlike.host/ws` |
| 公网地址 | `74.50.78.125:26375`（别名 `srv9007.godlike.club`） |
| 规格 | 2GB RAM / 512MB swap / 10GB 磁盘 / CPU 100% / 5 个额外端口 |
| egg | `PC-Paper`（nest 1 / egg 3），docker image `ghcr.io/ptero-eggs/yolks:java_25` |
| 免费标记 | `free=true`，`free_timer` = **2026-10-27 10:57:39 UTC / 10-27 18:57 北京** |

## 免费档领取方式（2026-10-26 实测可用）

产品是官网的 `productId=1127`（组名 `Free Tariffs`，产品名 `Minecraft (USA)`）：

1. `GET  /clientarea/product_features.php?action=cart&productId=1127` → 拿 location 列表（configid=2）
2. `POST /clientarea/api-cart-free.php {"product":1127,"config":<locId>}` → 加购
3. `POST /clientarea/product_features.php?action=free_order {"product":1127,"config":<locId>}` → 直接开通，返回面板 SSO 链接

可选 locId：`725` USA-EAST / `728` USA-WEST / `1742` USA-CENTER / `726` Canada（免费档只认这几个）。
两个 Gmail（btpp03 / btpp04）在 godlike 都是已注册状态，登录密码未知；能用的号是上面这个。

## 续期机制（实测数字，别再用旧笔记里的说法）

| 腿 | 端点 | 收益 | 冷却 |
| --- | --- | --- | --- |
| 视频 | `POST /servers/{uuid}/free-renewal/video/start {"initial_time":0}` + 每 30s `POST …/video/update-time {"renewal_uuid","video_time_watched","time_correction":0}` | 累计 **240s → +24h** | 24h（单次上报上限 300s，报 330 会 422） |
| 投票 | `POST /servers/{uuid}/free-renewal/vote {"type":"vote_listing"}` | **+3h** | 24h |
| 状态查询 | `GET …/free-renewal/status?type=vote_listing` → `can_vote` · `GET …/video/status?type=youtube_iter1` → `can_watch` | — | — |

- 续期**累加**到现有 `free_timer` 上，提前续不浪费 → 稳定态每天 +27h
- 服务端校验两次心跳的**真实间隔 25~35s**，所以 job 要真跑 4 分钟，不能一把梭
- 坑：路由前缀是 `free-renewal/`，裸 `video/start` 是 404；被 suspend 的服 `power start` 只回 400，得先解封

## 自动化

| 项 | 值 |
| --- | --- |
| 仓库 | https://github.com/btpp03/godlike-renew-hermes （public） |
| workflow | `renew.yml`（id `396614509`），`workflow_dispatch` + 原生 `schedule` `23 */6 * * *` |
| 外部定时腿 | cron-job.org job **8723656**，UTC `0/6/12/18` 的 `:13` → 北京 `08:13/14:13/20:13/02:13`，job 级 Basic 认证带 PAT |
| Secrets | `GODLIKE_EMAIL`、`GODLIKE_PASSWORD` |
| 环境变量 | `GODLIKE_WATCH_SECONDS`（默认 240）、`GODLIKE_KEEP_HOURS`（默认 30） |
| 验收记录 | 03:45:00Z tick → history `status=1 httpStatus=204 dur=1488ms` → GA run `40265640808` 33 秒后创建 success |

本账号 GA 原生 schedule 经常不 fire，所以 cron-job.org 才是真正的时间源；
该 job 设了 `onFailure`/`onDisable` 邮件，连续失败会被自动禁用，节点静默死亡时先去 console 看 `enabled` 位。
