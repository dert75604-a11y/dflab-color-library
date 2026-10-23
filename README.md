# 上海·DF-LAB 色彩数据库

免费公开的木作与涂装色彩参考。先对编号，再谈落地。

页面是仓库根目录的静态文件。数据在 `color-library-3.json`。对外文案以 `from-chatgpt/site-copy-P0.md` 为准。

本仓库只做展示和检索。测色、近邻色差、打板和配方不在这里。

## 本地打开

在仓库目录执行：

```bash
python3 -m http.server 8000
```

浏览器打开 http://127.0.0.1:8000/

不要用 `file://` 双击 `index.html`。浏览器会拦住页面读取旁边的 JSON，色卡列表出不来。

## 如何加一条色卡

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

## 部署

生产域名是 **https://shanghaidflab.cn** 。分享链接和页面 canonical 都用这个域，例如 `https://shanghaidflab.cn/#F-00001`。

公网目前查不到 `shanghaidflab.cn` 的 A / AAAA 记录（域名已注册，还没做解析）。在 DNS 生效之前，这个地址打不开是正常的，不是页面没发布。

仓库里没有 Vercel、Nginx 或单独的构建脚本。线上就是 GitHub Pages，发布源是 `main` 分支的根目录 `/`。

- 仓库：https://github.com/dert75604-a11y/dflab-color-library
- Pages 默认地址：https://dert75604-a11y.github.io/dflab-color-library/
- 根目录 `CNAME` 只有一行 `shanghaidflab.cn`，用来把 Pages 的自定义域名设成这个 apex

### 1. 本仓如何发布

没有编译步骤。`index.html`、`color-library-3.json` 和 `images/` 里的图片就是整站。页面用相对路径读 JSON。

合并到 `main` 并推上去之后，GitHub Pages 会把仓库根目录原样发布（根目录有 `.nojekyll`，不会再跑 Jekyll）。浏览器若还是旧页面，强刷一次。

Pages 一旦认下自定义域名，`github.io` 地址有时会跳到 `https://shanghaidflab.cn`。DNS 还没指过来时，这个跳转会打开失败。那一段先到域名控制台把记录加上，不要当成站点文件坏了。

### 2. 在域名控制台添加解析

先在 GitHub 上确认自定义域名，再改 DNS。GitHub 的建议是：先把域名加到这个仓库的 Pages，避免域名还没绑定时被别人占用。账号或仓库的 Pages 域名验证若要求 TXT，值以 GitHub 页面当场显示的为准。

仓库 Settings → Pages：

- Source：Deploy from a branch，Branch 为 `main`，目录 `/`
- Custom domain：`shanghaidflab.cn`
- DNS 生效、证书签发之后，再打开 Enforce HTTPS

然后到注册商或 DNS 控制台，给 **`shanghaidflab.cn`** 添加指向 GitHub Pages 的记录。主机名 `@` 表示 apex。

apex `shanghaidflab.cn`（四条 A，再加四条 AAAA）：

| 类型 | 主机 | 记录值 |
|------|------|--------|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| AAAA | `@` | `2606:50c0:8000::153` |
| AAAA | `@` | `2606:50c0:8001::153` |
| AAAA | `@` | `2606:50c0:8002::153` |
| AAAA | `@` | `2606:50c0:8003::153` |

控制台如果支持 ALIAS 或 ANAME，也可以改用一条：主机 `@`，指向 `dert75604-a11y.github.io`。用了 ALIAS 就不要再同时堆一组互相冲突的 A。国内注册商多数没有 ALIAS，用上面的 A + AAAA 即可。

可选 `www`：

| 类型 | 主机 | 记录值 |
|------|------|--------|
| CNAME | `www` | `dert75604-a11y.github.io` |

有的控制台要求末尾加点：`dert75604-a11y.github.io.`。仓库 `CNAME` 文件里仍然只写 apex `shanghaidflab.cn`，不要写成 `www`。

加记录之前，先删掉控制台自动生成、指向别处的 `@` A / AAAA，以及会抢 `www` 的旧 CNAME。不要加 `*.shanghaidflab.cn` 这种泛解析。

### 3. 怎样算挂上了

```bash
dig shanghaidflab.cn +noall +answer -t A
dig shanghaidflab.cn +noall +answer -t AAAA
```

能看到上面的 GitHub Pages 地址后，再打开：

- https://shanghaidflab.cn
- https://shanghaidflab.cn/#F-00001

首页应是「上海·DF-LAB 色彩数据库」。带编号的链接应打开那一条色卡。证书可能要等几分钟到几小时。HTTPS 可用之后，再在 Pages 里勾上 Enforce HTTPS。
