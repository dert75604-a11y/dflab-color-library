# 国内机部署｜飞书勾选上架 → shanghaidflab.cn

这包在阿里云上自己跑，不经过 GitHub，也不要开 GitHub Pages。

生产机：`106.15.198.252`  
网站根：`/var/www/shanghaidflab`  
站点：https://shanghaidflab.cn

解压目录用 `/opt/dflab-feishu-sync`。不要解压到网站根，也不要把整夹拷进去。上站只跑 `tools/deploy_public_colors.sh`。它只复制这三样：

- `data/colors.json`
- `assets/colors/`
- `assets/nfc-public-colors.js`

NFC 手势页和 `nfc-scroll-assets` 保持不动。页脚 `沪ICP备2026039729号-1` 和站名「上海·DF-LAB 色彩数据库」留在现有 `index.html` 上。

## 1. 放到服务器

```bash
sudo mkdir -p /opt/dflab-feishu-sync
sudo tar -xzf feishu-sync-domestic.tar.gz -C /opt/dflab-feishu-sync --strip-components=1
cd /opt/dflab-feishu-sync
python3 -m unittest tests/test_public_colors.py
```

需要 Python 3。不装第三方包。

包里的 `data/colors.json` 是空数组 `[]`。这是占位，不是已经上架的色。夹具色 `F-00042` 只在 `--fixture` 时出现，默认文件里没有它。`F-TEST01` 未勾选，不会出现。

## 2. 环境变量

在服务器建 `/etc/dflab/public-colors.env`，权限 `600`。不要把这个文件打包或提交。

```bash
sudo mkdir -p /etc/dflab
sudo touch /etc/dflab/public-colors.env
sudo chmod 600 /etc/dflab/public-colors.env
```

写入：

```bash
FEISHU_APP_ID=
FEISHU_APP_SECRET=
# 已有 token 时可以不填上面两项，改填下面其中一个：
# FEISHU_TENANT_ACCESS_TOKEN=
# FEISHU_USER_ACCESS_TOKEN=
```

飞书应用要有多维表格只读（`bitable:app:readonly` 或 `base:record:retrieve`）和附件下载权限。表已固定，一般不用改：

| 变量 | 默认 |
|------|------|
| `FEISHU_APP_TOKEN` | `AvvUbYVazaJF1PsqNdgcQBgUn4b` |
| `FEISHU_TABLE_ID` | `tbl8AxaiNxueFhaT` |
| `FEISHU_VIEW_ID` | `vewggbVU5M` |
| `FEISHU_STATUS_ALLOW` | `终板通过,已上架` |

只读这一张样板表。不要去改别的业务台账。`备注` 不会写进公网 JSON。

## 3. 先空跑，再真拉

在 `/opt/dflab-feishu-sync`：

```bash
python3 tools/feishu_public_colors.py sync \
  --fixture tests/fixtures/feishu-records.json \
  --dry-run

python3 tools/feishu_public_colors.py sync \
  --fixture tests/fixtures/feishu-records.json \
  --out-dir /tmp/dflab-color-preview
```

`--fixture` 不访问飞书。`--dry-run` 只往终端打 JSON，不写文件。看输出里有 `F-00042`，没有 `F-TEST01`，也没有备注原文。

真拉表：

```bash
set -a
. /etc/dflab/public-colors.env
set +a
python3 tools/feishu_public_colors.py sync
```

没有密钥时会退出，并提示缺 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`。不要用夹具结果覆盖网站。

勾选规则：`公开上架` 为真，`code` 是 `F-` 加五位数字，有色名、finish、主图，状态是「终板通过」或「已上架」。取消勾选后，下一轮 JSON 里没有这一条，图也会从 `assets/colors/` 删掉。

`--writeback-status` 会把刚公开成功的行改成「已上架」。默认不改飞书。

## 4. 拷到网站

先同步出真数据，再部署。空的 `data/colors.json` 一旦部署，会把网站上的 `assets/colors/` 清掉。

```bash
cd /opt/dflab-feishu-sync
DEPLOY_LOCAL=1 DEPLOY_LOCAL_DIR=/var/www/shanghaidflab \
  ./tools/deploy_public_colors.sh --dry-run

DEPLOY_LOCAL=1 DEPLOY_LOCAL_DIR=/var/www/shanghaidflab \
  ./tools/deploy_public_colors.sh
```

脚本拒绝别的远程目录。远程路径只能是 `/var/www/shanghaidflab`。人就在这台机器上时用上面的 `DEPLOY_LOCAL=1`，不用 SSH。

第一次让「查看全部色卡」读这份 JSON 时，加 `PATCH_NFC=1`：

```bash
DEPLOY_LOCAL=1 DEPLOY_LOCAL_DIR=/var/www/shanghaidflab PATCH_NFC=1 \
  ./tools/deploy_public_colors.sh
```

它只在现有 NFC 页的 `</body>` 前插入：

```html
<script src="assets/nfc-public-colors.js"></script>
```

页面上必须已经有备案号、站名和 `nfc-scroll-assets`，否则拒绝改文件。插过一次再跑也不会插第二遍。手势缩放、宏图横滑、木种横滑不改。`data/colors.json` 有公开色时，只重画「查看全部色卡」；文件是空的或打不开时，浮层保持原样。

## 5. 定时

```cron
*/5 * * * * . /etc/dflab/public-colors.env && cd /opt/dflab-feishu-sync && python3 tools/feishu_public_colors.py sync && DEPLOY_LOCAL=1 DEPLOY_LOCAL_DIR=/var/www/shanghaidflab PATCH_NFC=1 ./tools/deploy_public_colors.sh
```

`PATCH_NFC=1` 可以留在 cron 里。已经插入桥接脚本时，它不会再改 `index.html`。
