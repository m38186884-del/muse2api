#!/usr/bin/env python3
"""muse2api hardened fork: re-apply security patches.

WHAT: permanently disables the one-click online updater and every other
      channel that can pull code from / push code to the upstream repo
      (czg86389-hub/muse2api), so a deployed node can never be modified
      by upstream again.

WHEN TO RUN: after `git merge upstream/main` (or cherry-pick), BEFORE
      deploying. The script asserts each upstream code shape it patches;
      if upstream refactored the updater code, an assertion fails LOUDLY
      and nothing is half-applied. Fail closed, never silently skip.

      Do NOT run on an already-patched tree (it aborts on purpose).

USAGE:  python3 fork-maint/apply-fork-patches.py   # from repo root
"""
import json
import os
import re
import sys

FORK_URL = "https://github.com/m38186884-del/muse2api"
UPSTREAM_URL = "https://github.com/czg86389-hub/muse2api"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app.py")
ADMIN = os.path.join(ROOT, "admin.html")
VER = os.path.join(ROOT, "version.json")

MARK = "[FORK 安全补丁]"


def die(msg: str) -> None:
    print(f"ABORT: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    src = open(APP, encoding="utf-8").read()
    if MARK in src:
        die("app.py already patched — run only after merging upstream/main.")

    # ---- A. _check_update_sync: local-only, no upstream requests ----
    new_check = '''def _check_update_sync(force: bool = False) -> dict:
    """[FORK 安全补丁] 在线更新检测已永久禁用。
    本 fork 不再向任何上游 GitHub 仓库发起版本检查请求，仅返回本地版本信息。
    如需跟进上游更新，请人工 review 上游 diff 后手动合并。
    """
    now = time.time()
    local_ver_obj = _read_local_version()
    local_version = str(local_ver_obj.get("version") or "1.5.0")

    has_git = os.path.isdir(os.path.join(BASE_DIR, ".git"))
    local_sha, local_msg, local_ts = "", "", 0
    if has_git:
        try:
            r_sha = _git(["rev-parse", "--short", "HEAD"])
            if r_sha.returncode == 0:
                local_sha = r_sha.stdout.strip()[:7]
            r_log = _git(["log", "-1", "--format=%s||%ct"])
            if r_log.returncode == 0 and "||" in r_log.stdout:
                parts = r_log.stdout.strip().split("||", 1)
                local_msg = parts[0]
                local_ts = int(parts[1])
        except Exception:
            pass

    if not local_sha and os.path.isfile(_installed_sha_file()):
        try:
            with open(_installed_sha_file(), encoding="utf-8") as f:
                local_sha = f.read().strip()[:7]
        except OSError:
            pass

    data = {
        "repo_url": REPO_URL,
        "has_git": has_git,
        "local_version": local_version,
        "remote_version": local_version,
        "local_sha": local_sha,
        "local_msg": local_msg,
        "local_ts": local_ts,
        "remote_sha": "",
        "remote_msg": "",
        "remote_time": "",
        "has_update": False,
        "up_to_date": True,
        "updater_disabled": True,
        "updater_note": "一键在线升级已在此 fork 中永久禁用；如需更新请人工 review 上游 diff 后手动合并",
        "highlights": list(local_ver_obj.get("highlights") or []),
        "recent_commits": [],
        "checked_at": int(now),
    }
    _UPDATE_CACHE["ts"] = now
    _UPDATE_CACHE["data"] = data
    return data


'''
    p = re.compile(
        r'def _check_update_sync\(force: bool = False\) -> dict:.*?(?=\ndef _upgrade_from_github_sync\(\) -> dict:)',
        re.DOTALL,
    )
    src, n = p.subn(new_check, src)
    if n != 1:
        die(f"_check_update_sync shape changed upstream (matches={n}) — review manually.")

    # ---- B. _upgrade_from_github_sync: hard 403 ----
    new_sync = '''def _upgrade_from_github_sync() -> dict:
    """[FORK 安全补丁] 已永久禁用：任何情况下都不再从上游 GitHub 拉取代码覆盖本地文件。"""
    raise HTTPException(403, "一键在线升级已在此 fork 中永久禁用。如需更新，请人工 review 上游仓库 diff 后手动合并部署。")


'''
    p = re.compile(
        r'def _upgrade_from_github_sync\(\) -> dict:.*?(?=\n@app\.get\("/admin/update/check"\)\n)',
        re.DOTALL,
    )
    src, n = p.subn(new_sync, src)
    if n != 1:
        die(f"_upgrade_from_github_sync shape changed upstream (matches={n}) — review manually.")

    # ---- C. /admin/update/upgrade + /admin/repo/pull: hard 403 ----
    new_ep = '''async def admin_upgrade_now(payload: dict = Body(default={}), _=Depends(auth)):
    """[FORK 安全补丁] 一键在线升级已永久禁用。"""
    raise HTTPException(403, "一键在线升级已在此 fork 中永久禁用。如需更新，请人工 review 上游仓库 diff 后手动合并部署。")'''
    p = re.compile(
        r'async def admin_upgrade_now\(payload: dict = Body\(default=\{\}\), _=Depends\(auth\)\):\n'
        r'    """.*?"""\n.*?(?=\n\n\n@app\.post\("/admin/repo/push"\)\n)',
        re.DOTALL,
    )
    src, n = p.subn(new_ep, src)
    if n != 1:
        die(f"admin_upgrade_now shape changed upstream (matches={n}) — review manually.")

    # ---- D. /admin/repo/push: disabled (rewrites git origin, pushes outward) ----
    new_push = '''async def admin_repo_push(payload: dict = Body(default={}), _=Depends(auth)):
    """[FORK 安全补丁] 已禁用：如需同步代码请手动 git push。"""
    raise HTTPException(403, "该接口已在此 fork 中禁用。如需同步代码，请手动 git push。")'''
    p = re.compile(
        r'async def admin_repo_push\(payload: dict = Body\(default=\{\}\), _=Depends\(auth\)\):\n'
        r'    """.*?"""\n.*?(?=\n\n\n@app\.on_event\("startup"\)\n)',
        re.DOTALL,
    )
    src, n = p.subn(new_push, src)
    if n != 1:
        die(f"admin_repo_push shape changed upstream (matches={n}) — review manually.")

    # ---- E. _ensure_git_repo: disabled (rewrote origin to upstream) ----
    old_repo_fn = '''def _ensure_git_repo(token: str = ""):
    """确保 BASE_DIR 已初始化为绑定 czg86389-hub/muse2api 的 Git 仓库。"""
    git_dir = os.path.join(BASE_DIR, ".git")
    remote_url = f"https://x-access-token:{token}@github.com/czg86389-hub/muse2api.git" if token else f"{REPO_URL}.git"
    if not os.path.isdir(git_dir):
        _git(["init", "-b", "main"])
        _git(["remote", "add", "origin", remote_url])
        _git(["fetch", "origin", "main"], timeout=45)
        _git(["reset", "--mixed", "origin/main"])
    else:
        _git(["remote", "set-url", "origin", remote_url])
    _git(["config", "user.name", "czg86389-hub"])
    _git(["config", "user.email", "czg86389-hub@users.noreply.github.com"])'''
    new_repo_fn = '''def _ensure_git_repo(token: str = ""):
    """[FORK 安全补丁] 已禁用：不再自动绑定/改写 git origin。"""
    raise HTTPException(403, "该操作已在此 fork 中禁用。")'''
    if src.count(old_repo_fn) != 1:
        die("_ensure_git_repo shape changed upstream — review manually.")
    src = src.replace(old_repo_fn, new_repo_fn)

    # ---- F. REPO_URL -> fork ----
    if src.count(f'REPO_URL = "{UPSTREAM_URL}"') != 1:
        die("REPO_URL line changed upstream — review manually.")
    src = src.replace(f'REPO_URL = "{UPSTREAM_URL}"', f'REPO_URL = "{FORK_URL}"')

    open(APP, "w", encoding="utf-8").write(src)
    print("app.py: patched")

    # ---- G..K. admin.html ----
    html = open(ADMIN, encoding="utf-8").read()
    if MARK in html:
        die("admin.html already patched — run only after merging upstream/main.")

    # G. remove browser-side fallback that queries upstream GitHub API
    p = re.compile(r'    // 若服务端网络无法直连 GitHub API[\s\S]*?\n    \}\n')
    html, n = p.subn('    // [FORK 安全补丁] 浏览器端兜底检测已移除：不再向官方仓库查询更新。\n', html)
    if n != 1:
        die("admin.html fallback block changed upstream — review manually.")

    # H. hide both upgrade buttons
    for bid in ("btnBannerUpgrade", "btnRepoPull"):
        old = f'<button onclick="upgradeNow()" id="{bid}">'
        if html.count(old) != 1:
            die(f"admin.html button {bid} changed upstream — review manually.")
        html = html.replace(old, f'<button onclick="upgradeNow()" id="{bid}" style="display:none">')

    # I. panel title
    if html.count("官方仓库版本检测与在线热升级") != 1:
        die("admin.html panel title changed upstream — review manually.")
    html = html.replace("官方仓库版本检测与在线热升级", "版本状态（在线升级已在此 fork 中禁用）")

    # J. upgradeNow(): toast-only, defense in depth
    p = re.compile(r'async function upgradeNow\(\)\{.*?\n\}', re.DOTALL)
    new_fn = '''async function upgradeNow(){
  toast('一键在线升级已在此 fork 中永久禁用。如需更新请人工 review 上游 diff 后手动合并。', 'warn');
}'''
    html, n = p.subn(new_fn, html, count=1)
    if n != 1:
        die("admin.html upgradeNow() changed upstream — review manually.")

    # K. upstream hyperlinks -> fork
    html = html.replace(UPSTREAM_URL, FORK_URL)
    html = html.replace("czg86389-hub/muse2api ↗", "m38186884-del/muse2api (fork) ↗")

    open(ADMIN, "w", encoding="utf-8").write(html)
    print("admin.html: patched")

    # ---- L. version.json ----
    ver = json.loads(open(VER, encoding="utf-8").read())
    if not str(ver.get("version", "")).endswith("-fork"):
        ver["version"] = str(ver.get("version")) + "-fork"
    ver["repo"] = FORK_URL
    open(VER, "w", encoding="utf-8").write(json.dumps(ver, ensure_ascii=False, indent=2) + "\n")
    print("version.json: patched")

    print("OK — all fork patches applied. Verify with: python3 -m py_compile app.py")
    print("Then commit. NEVER deploy straight from upstream.")


if __name__ == "__main__":
    main()
