# godlike-renew-hermes

Godlike Host 免费 Minecraft 服（2GB，US 区）的**自动续期 + 保活**，纯 API，不依赖浏览器。

## 它做什么

登录面板 → 列出账号下所有 `free=true` 的服务器 → 对每台：

1. **保活**：状态不是 `running` 就 `POST /servers/{uuid}/power {"signal":"start"}`
2. **投票续期**（+3h，24h 冷却）：`POST /servers/{uuid}/free-renewal/vote {"type":"vote_listing"}`
3. **看视频续期**（+24h，24h 冷却）：`video/start` 拿 session → 每 30s 打一次 `video/update-time`，累计 240s 即结算（服务端单次上限 300s）

续期是**累加**到现有 `free_timer` 上（240s → +24h），所以提前续不会浪费。剩余 > `GODLIKE_KEEP_HOURS`（默认 30h）时整轮跳过；默认值下每轮都会试，冷却期内失败不扣任何东西。

## 为什么是轮询心跳而不是一把梭

服务端校验两次 `update-time` 的**真实间隔必须在 25~35 秒之间**，且 `video_time_watched` 的增量也要落在这个窗口里。所有"一次性把 240 秒报上去"的写法都会被判无效，所以 job 要真跑 4 分钟。

## 用法

- 手动：Actions → `renew` → Run workflow（可改 `watch_seconds` / `keep_hours`）
- 定时：本仓 `schedule` 是 `23 */6 * * *`，但**本账号 GA 原生 schedule 经常不 fire**，
  真正的时间源是 cron-job.org 的 dispatch job（每 6h 派发 `workflow_dispatch`）。

## Secrets

| 名字 | 说明 |
| --- | --- |
| `GODLIKE_EMAIL` | 面板登录邮箱（`nicebtpp@proton.me`） |
| `GODLIKE_PASSWORD` | 面板登录密码 |

## 环境变量

| 名字 | 默认 | 说明 |
| --- | --- | --- |
| `GODLIKE_WATCH_SECONDS` | `240` | 累计观看秒数，240 就给 +24h（上限 300） |
| `GODLIKE_KEEP_HOURS` | `30` | 剩余超过该小时数就跳过本轮 |

## 关键端点（面板 ultra.panel.godlike.host 的 `/api/v2`）

所有请求都要带 `Authorization: Bearer ptlc_...` 以及
`Accept: application/json` + `X-Requested-With: XMLHttpRequest` + `Origin/Referer: https://ultra.panel.godlike.host`，
缺了会被回 SPA HTML。

- `POST /auth/login` `{"user":email,"password":pw}` → `data.token`
- `GET /servers` / `GET /servers/{uuid}`（`free_timer` 就是到期时间，UTC）
- `GET /servers/{uuid}/free-renewal/status?type=vote_listing` → `can_vote`
- `POST /servers/{uuid}/free-renewal/vote` `{"type":"vote_listing"}`
- `GET /servers/{uuid}/free-renewal/video/status?type=youtube_iter1` → `can_watch`
- `POST /servers/{uuid}/free-renewal/video/start` `{"initial_time":0}` → `{uuid}`
- `POST /servers/{uuid}/free-renewal/video/update-time` `{"renewal_uuid","video_time_watched","time_correction":0}`

⚠️ 之前踩过的坑：续期路由前缀是 `free-renewal/`，裸 `video/start` 是 404；被 suspend 的服
`power start` 只回 400，得先走解封流程。
