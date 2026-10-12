# muse2api · hardened fork

把 muse.ai 网页端逆向封装为 OpenAI 兼容 API（对话 / 文生图 / 文生视频），通过无头 Chromium + CDP 驱动。

**这是 [czg86389-hub/muse2api](https://github.com/czg86389-hub/muse2api) 的安全加固 fork。**
一键在线升级已被**永久禁用**——部署出去的节点永远无法自己从上游拉代码。
上游原版 README 留在 [README_UPSTREAM.md](./README_UPSTREAM.md)（接口文档看那份）。

## 部署（Docker，推荐）

```bash
git clone https://github.com/m38186884-del/muse2api.git
cd muse2api
cp .env.example .env
# 编辑 .env：把 MUSE2API_KEY 换成你自己的强随机值（m2a_ 开头）
docker compose up -d --build
```

管理面板：`http://<服务器IP>:18610/admin?key=<你的MUSE2API_KEY>`

## 部署（裸机 Ubuntu/Debian）

```bash
sudo apt-get update && sudo apt-get install -y chromium python3 python3-pip python3-venv
git clone https://github.com/m38186884-del/muse2api.git /opt/muse2api
cd /opt/muse2api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 设置 MUSE2API_KEY
# 按实际情况改 deploy/muse2api.service 里的 User/路径后：
sudo cp deploy/muse2api.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now muse2api
```

走 Nginx 反代时必须：`proxy_read_timeout 600s;` + `proxy_buffering off;`
（否则生图/视频长请求会被 502，SSE 流式输出会卡顿；模板见 `deploy/nginx.example.conf`）

## 必做配置

| 变量 | 说明 |
|---|---|
| `MUSE2API_KEY` | **必填**，强随机值。留空则首次启动自动生成并打印到日志——生产环境请自己设置 |
| `MUSE2API_HOST` / `MUSE2API_PORT` | 默认 `0.0.0.0:18610`。**不要把 18610 直接暴露到公网**，必须走反代 |
| `MUSE2API_PUBLIC_BASE` | 对外域名，如 `https://api.yourdomain.com`（管理页拼接地址用） |

注意：CORS 默认全放开，`MUSE2API_KEY` 是唯一的鉴权——端口裸奔 = 账号裸奔。

## 账号导入

1. Chrome/Edge 开开发者模式，加载已解压的扩展程序 → 选 `extension/` 目录
2. 登录 muse.ai，点扩展图标，填服务地址 + `MUSE2API_KEY` →「读取并导入」
3. 或用油猴脚本 `tools/muse2api_cookie_importer.user.js`

Cookie 明文存于 `data/accounts.json`，备份/迁移时注意保密。**只用测试号**，见下方安全红线。

## API 调用

所有接口 Header 携带 `Authorization: Bearer <MUSE2API_KEY>`：

```bash
# 对话
curl -X POST http://localhost:18610/v1/chat/completions \
  -H "Authorization: Bearer $MUSE2API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"muse-spark","messages":[{"role":"user","content":"你好"}]}'

# 文生图
curl -X POST http://localhost:18610/v1/images/generations \
  -H "Authorization: Bearer $MUSE2API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"muse-image","prompt":"一只柴犬","size":"16:9"}'

# 视频（异步）：POST /v1/videos 创建任务 → 轮询 GET /v1/videos/{id}
```

## 本 fork 与上游的差异

- `_check_update_sync`：不再请求上游 GitHub，只返回本地版本（`has_update` 恒为 false）
- `/admin/update/upgrade`、`/admin/repo/pull`、`/admin/repo/push`：一律 403
- `_upgrade_from_github_sync`、`_ensure_git_repo`：已禁用（后者曾把 git origin 改写指向上游）
- `admin.html`：删除浏览器端兜底检测、一键升级按钮隐藏、`upgradeNow()` 只弹提示
- `REPO_URL`、版本信息、超链接：全部指向本 fork；版本号 `1.6.0-fork`

## 上游更新同步（手动，必读）

```bash
git remote add upstream https://github.com/czg86389-hub/muse2api.git  # 只需一次
git fetch upstream
git log --oneline main..upstream/main     # 看提交
git diff main..upstream/main --stat       # 看改了哪些文件
# ★ 人工 review diff，确认无恶意代码/无私货后再合并：
git merge upstream/main
python3 fork-maint/apply-fork-patches.py  # 重新打补丁（merge 会把 updater 带回来）
                                          # 断言失败会直接报错停下，不会静默跳过
git add -A && git commit -m "merge upstream + re-apply fork patches"
```

## 安全红线

1. 这是逆向 muse.ai 网页端的项目，违反 Meta 服务条款——**只用测试号**，主力号别碰。
2. 永远不要从上游直接 `git pull` 到生产机；更新只走上面的手动流程。
3. `data/` 目录（含账号 cookie、任务记录、媒体文件）不进版本库，备份时加密存放。
