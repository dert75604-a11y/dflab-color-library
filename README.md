# 上海·DF-LAB 色彩数据库

免费公开的木作与涂装色彩参考。先对编号，再谈落地。

页面是仓库根目录的静态文件。飞书勾了「公开上架」的色卡写在 `data/colors.json`。这份文件还是空数组时，旧页面回退读 `color-library-3.json`。对外文案以 `from-chatgpt/site-copy-P0.md` 为准。

线上现在是阿里云上的 NFC 预览，不是这个旧检索页，也不是 GitHub Pages。NFC 手势页继续用服务器上的 `index.html` 和 `nfc-scroll-assets`。公开色卡只加数据层。

本仓库只做展示和检索。测色、近邻色差、打板和配方不在这里。

## 本地打开

在仓库目录执行：

```bash
python3 -m http.server 8000
```

浏览器打开 http://127.0.0.1:8000/

不要用 `file://` 双击 `index.html`。浏览器会拦住页面读取旁边的 JSON，色卡列表出不来。

## 如何加一条色卡

线上新色不要手改 JSON。在飞书勾「公开上架」，由下一节的脚本写出 `data/colors.json`。下面只留给回退库 `color-library-3.json`：公开文件还是空数组时，旧检索页才读它。

编辑 `color-library-3.json`，它是一个数组。在数组末尾追加一条。图片优先放进 `images/`，用相对路径；也可以写 `https` 外链。已有条目里的 data URL 仍能显示。新条目不要再塞大段 base64。

```json
{
  "code": "F-00031",
  "name": "色名",
  "color": "#8b7355",
  "finish": "哑光开放",
  "image": "images/F-00031.jpg",
  "tags": ["柚木", "暖色"],
  "uploader": "DF-LAB"
}
```

要点摘自 `from-chatgpt/content-sop-色卡上传.md`：

- `code`：`F-` 加五位数字，例如 `F-00031`。全库唯一，只增不改号。
- `name`：对外能念的色名，2～12 字为宜。
- `color`：示意用的 hex，不是验收依据。
- `finish`：必填，例如「哑光开放」。
- `image`：必有规范图。文件名建议 `{code}.jpg`。
- `tags`：建议至少 1 个，树种、色系或场景。
- `uploader`：填 `DF-LAB`。

缺图、缺编号、缺 `finish` 不上架。图里不要出现配方瓶、克数标签或调色单。不要写对色百分比。页面只展示上面这些字段，JSON 里不要加配方或克数。

拍摄光线、何时不上架、每周节奏，见 `from-chatgpt/content-sop-色卡上传.md`。

## 飞书勾选上架

人在飞书表「样板」里勾「公开上架」。脚本下一轮把勾中的、字段齐全的行写成公开 JSON 和图。取消勾选后，下一轮 JSON 里没有这一条，对应图片也从 `assets/colors/` 删掉。

表（只读这一张，不要去改别的业务台账）：

| 项 | 值 |
|----|-----|
| app_token | `AvvUbYVazaJF1PsqNdgcQBgUn4b` |
| table_id | `tbl8AxaiNxueFhaT` |
| view | `vewggbVU5M` |

会公开的字段：`code`、`name`、`color`（来自 hex）、`finish`、`species`（来自树种）、`image`、`imageCloseup`（有特写才有）、`uploader`、`tags`。`备注` 不写进 JSON，也不进同步报告。图只落成文件，路径像 `/assets/colors/F-00001.jpg`，不塞 base64。

一条要同时满足才上架：`公开上架` 为真，`code` 是 `F-` 加五位数字，有 `name`、`finish`、主图，并且 `状态` 是「终板通过」或「已上架」。缺任何一项就跳过。`F-TEST01` 在未勾选时原因是 `not_public`，不会出现。它的编号也不是五位数字，就算误勾，也会因 `code_format` 被丢掉。

触发方式是定时拉，不是勾选瞬间的 webhook。建议在国内机上每 5 分钟跑一次（机器要能访问飞书开放平台）。勾选后，最迟在这一轮里上站。

### 环境变量

密钥只放环境，不进仓库。

| 变量 | 作用 |
|------|------|
| `FEISHU_APP_ID` | 飞书应用 App ID。和 `FEISHU_APP_SECRET` 一起换 tenant token |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret |
| `FEISHU_TENANT_ACCESS_TOKEN` | 已有的 tenant token。设了就不再用 id/secret |
| `FEISHU_USER_ACCESS_TOKEN` | 已有的 user token。没设 tenant token 时用它 |
| `FEISHU_APP_TOKEN` | 默认同上表，一般不用改 |
| `FEISHU_TABLE_ID` | 默认同上表 |
| `FEISHU_VIEW_ID` | 默认同上表 |
| `FEISHU_BASE_URL` | 默认 `https://open.feishu.cn` |
| `FEISHU_STATUS_ALLOW` | 允许上架的状态，逗号分隔。默认 `终板通过,已上架` |
| `DEPLOY_SSH_USER` | 登录 `106.15.198.252` 的用户 |
| `DEPLOY_SSH_KEY` | 私钥路径。不设就用 ssh 默认密钥 |
| `DEPLOY_HOST` | 默认 `106.15.198.252` |
| `DEPLOY_PORT` | 默认 `22` |

应用至少要有多维表格只读（`bitable:app:readonly` 或 `base:record:retrieve`），以及附件下载权限。没有这两项，脚本连上也会被飞书拒绝。

`--writeback-status` 会把刚上架成功、且状态还不是「已上架」的行改成「已上架」。默认不改表。

### 本地怎么跑

在仓库根目录：

```bash
python3 -m unittest tests/test_public_colors.py

python3 tools/feishu_public_colors.py sync \
  --fixture tests/fixtures/feishu-records.json \
  --dry-run

python3 tools/feishu_public_colors.py sync \
  --fixture tests/fixtures/feishu-records.json \
  --out-dir /tmp/dflab-color-preview
```

`--fixture` 不访问飞书。`--dry-run` 只把将要公开的 JSON 打到标准输出，不写文件。正式拉表：

```bash
export FEISHU_APP_ID=...
export FEISHU_APP_SECRET=...
python3 tools/feishu_public_colors.py sync
```

成功后仓库里是 `data/colors.json` 和 `assets/colors/`。旧检索页会优先读这份 JSON；空数组时仍回退 `color-library-3.json`。

### 没有密钥时

云端这次没有可用的飞书表格权限，也没有能登录 `106.15.198.252` 的 SSH 密钥。代码和夹具可以跑，真表和真机部署要等环境变量补上。夹具里的 `F-00042` 能导出；`F-TEST01` 未勾选，不会出现。

## 部署

生产是 **https://shanghaidflab.cn** ，主机 `106.15.198.252`，nginx 根目录 **`/var/www/shanghaidflab`**。只往这个目录拷数据。不要开 GitHub Pages，不要把整仓 rsync 上去，否则会盖掉线上的 NFC `index.html` 和 `nfc-scroll-assets`。

页脚备案 `沪ICP备2026039729号-1` 和站名「上海·DF-LAB 色彩数据库」留在现有 NFC 页上。本脚本不改这两处，除非显式加上 `PATCH_NFC=1`。`PATCH_NFC=1` 也只在确认是 NFC 生产页之后，于 `</body>` 前插入一行：

```html
<script src="assets/nfc-public-colors.js"></script>
```

这行脚本在 `data/colors.json` 有公开色时，重画「查看全部色卡」。手势缩放、宏图横滑、木种横滑仍走原来的 `nfc-scroll-assets`。JSON 为空或加载失败时，浮层保持原样。

在服务器上（推荐，cron 不用 SSH）：

```bash
cd /opt/dflab-color-library
set -a
. /etc/dflab/public-colors.env
set +a
python3 tools/feishu_public_colors.py sync
DEPLOY_LOCAL=1 DEPLOY_LOCAL_DIR=/var/www/shanghaidflab \
  ./tools/deploy_public_colors.sh
```

第一次接上浮层时再加 `PATCH_NFC=1`。之后同一行可以留着，已经插过就不会再改 `index.html`。

从别的机器推：

```bash
export DEPLOY_SSH_USER=...
export DEPLOY_SSH_KEY=/path/to/key
./tools/deploy_public_colors.sh --dry-run
./tools/deploy_public_colors.sh
```

远程目标写死为 `106.15.198.252:/var/www/shanghaidflab`。拷过去的只有：

- `data/colors.json`
- `assets/colors/`
- `assets/nfc-public-colors.js`

cron 示例（服务器上，每 5 分钟）：

```cron
*/5 * * * * . /etc/dflab/public-colors.env && cd /opt/dflab-color-library && python3 tools/feishu_public_colors.py sync && DEPLOY_LOCAL=1 DEPLOY_LOCAL_DIR=/var/www/shanghaidflab ./tools/deploy_public_colors.sh
```

`/etc/dflab/public-colors.env` 自己建，不要提交。

分享链接仍用 `https://shanghaidflab.cn/#F-00001`。旧检索页认这个 hash；NFC 手势页以浮层和主图为准。
