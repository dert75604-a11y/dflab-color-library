# 上海·DF-LAB 色彩数据库

线上首页是 NFC 单色色卡页（浅底、手机框、主图与特写、木种色卡条）。标题是「上海·DF-LAB 色彩数据库」，页脚备案号是 `沪ICP备2026039729号-1`。

生产域名是 **https://shanghaidflab.cn** ，由阿里云 Nginx 直接托管本仓库根目录的静态文件。没有编译步骤。

## 仓库里什么是首页

| 路径 | 作用 |
|------|------|
| `index.html` | 线上首页。色卡图、logo、棘轮音效都用相对路径 `nfc-scroll-assets/`，不要改成绝对地址。 |
| `nfc-scroll-assets/` | 首页用到的 jpg、logo、`ratchet-tick.wav`。 |
| `color-library-3.json` | 留给以后飞书同步。**不是首页**，页面不会去读它。 |
| `from-chatgpt/` | 旧版 JSON 色卡库的文案和上传说明，仅作存档。 |

旧的单页 JSON 浏览器已经从 `index.html` 换掉。根目录不再放 GitHub Pages 用的 `CNAME`：域名解析在阿里云，不在 Pages。

## 本地打开

在仓库目录执行：

```bash
python3 -m http.server 8000
```

浏览器打开 http://127.0.0.1:8000/

首页应出现「金柚 / 缅甸黄柚」，往下能看到色卡条和备案号。图片和音效走相对路径，用上面的本地服务打开即可。

## 部署到阿里云

网站根目录是 `/var/www/shanghaidflab`。在阿里云 Workbench 里用 `codeload.github.com` 拉取**这一次要上线的 commit**（公开仓库，不需要本机或 token）。把下面的 `COMMIT_SHA` 换成该提交的 40 位哈希。合并进 `main` 之后，也可以改用 `main` 上的最新提交。

```bash
set -euo pipefail
SHA=COMMIT_SHA
SITE=/var/www/shanghaidflab
STAMP=$(date +%Y%m%d%H%M%S)

sudo cp -a "$SITE" "/var/www/shanghaidflab.bak-${STAMP}"

WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT
cd "$WORKDIR"
wget -O site.tar.gz "https://codeload.github.com/dert75604-a11y/dflab-color-library/tar.gz/${SHA}"
tar -xzf site.tar.gz
SRC="$WORKDIR/dflab-color-library-${SHA}"
test -f "$SRC/index.html"
test -f "$SRC/nfc-scroll-assets/img-00.jpg"
test -f "$SRC/nfc-scroll-assets/df-lab-logo.png"

sudo find "$SITE" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
sudo cp -a "$SRC"/. "$SITE"/
sudo find "$SITE" -type d -exec chmod 755 {} +
sudo find "$SITE" -type f -exec chmod 644 {} +

sudo nginx -t
sudo systemctl reload nginx

curl -fsS -o /dev/null -w "home %{http_code}\n" https://shanghaidflab.cn/
curl -fsS https://shanghaidflab.cn/ | grep -F '<title>上海·DF-LAB 色彩数据库</title>'
curl -fsS https://shanghaidflab.cn/ | grep -F '沪ICP备2026039729号-1'
curl -fsS -o /dev/null -w "img %{http_code}\n" https://shanghaidflab.cn/nfc-scroll-assets/img-00.jpg
curl -fsS -o /dev/null -w "logo %{http_code}\n" https://shanghaidflab.cn/nfc-scroll-assets/df-lab-logo.png
curl -fsS -o /dev/null -w "tick %{http_code}\n" https://shanghaidflab.cn/nfc-scroll-assets/ratchet-tick.wav
```

期望：`home`、`img`、`logo`、`tick` 都是 `200`，两条 `grep` 都能打出标题和备案号。

回滚时把备份目录拷回 `$SITE`，再 `sudo nginx -t && sudo systemctl reload nginx`。备份在 `/var/www/shanghaidflab.bak-<时间戳>`。

若仓库 Settings 里 GitHub Pages 仍绑着 `shanghaidflab.cn`，关掉 Pages 的自定义域名（或停掉 Pages）。线上只走阿里云这台 Nginx。
