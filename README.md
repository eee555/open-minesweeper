# <a href="https://github.com/eee555/saolei_website" >开源扫雷网（Open Minesweeper）</a>

[![saolei_website](https://img.shields.io/badge/saolei_website-v1.7-brightgreen.svg)](https://github.com/eee555/Solvable-Minesweeper)
[![stars](https://img.shields.io/github/stars/eee555/saolei_website)](https://github.com/eee555/saolei_website/stargazers)
[![forks](https://img.shields.io/github/forks/eee555/saolei_website)](https://github.com/eee555/saolei_website/forks)

[![Dependabot Updates](https://github.com/eee555/saolei_website/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/eee555/saolei_website/actions/workflows/dependabot/dependabot-updates)

[English](Readme_en.md)

开源扫雷网（Open Minesweeper）成立于2023年12月3日，是由资深扫雷玩家志愿维护的非营利性录像排名平台。玩家上传扫雷录像，系统自动解析并生成竞速排名，支持标准、盲扫、无猜、密度、PB等榜单，同时提供金羊杯（GSC）锦标赛、周赛等赛事服务。与传统的中心化网站相比，开源扫雷网秉承​​社区驱动​​的核心理念，构建的是一个开放的协作生态。欢迎​​开发者、赞助者、赛事主办方​​乃至​​每一位用户​​的加入。

**社区驱动，民主治理。** 与传统的中心化网站不同，项目的一切决策，包括功能方向与站长、管理员人选，理论上均可以由核心团队投票决定。

我们相信扫雷社区的力量。无论你是开发者、赛事主办方、内容创作者还是普通玩家，这里都有你的位置。加入我们的方法：见[网站](https://openms.top)最下方的“联系我们”。

> **前端**：Vue 3 + TypeScript + Vite + Element Plus + PrimeVue + Tailwind CSS + WASM  
> **后端**：Django + django-ninja + MySQL + Redis  
> **录像解析**：ms-toollib（Rust 编译的 WASM / Python 库）  
> **部署**：Nginx + uWSGI + acme.sh  
> **内容审核**：百度大脑  
> **协议**：MIT License

本地要同时开后端、前端和勋章工人，测试账号和地址见 [本地启动.md](本地启动.md)。

## 项目安装流程：

本项目可在 Windows 上开发，在 Linux 上部署。先安装 Python、Node.js、MySQL 和 Redis，并将项目克隆到本地。以下开发命令使用 Windows PowerShell，起始目录为项目根目录。

后端：

1. 进入后端目录并创建虚拟环境；已有 `.venv` 时无需重新创建：

   ```powershell
   cd back_end\saolei
   python -m venv .venv
   ```

1. 先下载发布 wheel，再安装依赖。`requirements-wheels.txt` 固定 `wom-api` 和 `msgames-api` 的 GitHub 发布地址和 SHA-256；`requirements.txt` 固定安装版本。`wheels/` 不提交到 Git：

   ```powershell
   .\.venv\Scripts\python.exe -m pip download --no-deps --dest wheels -r requirements-wheels.txt
   .\.venv\Scripts\python.exe -m pip install --find-links wheels -r requirements.txt
   ```

   开发端需要能访问 GitHub 下载这些 wheel；其余依赖通过 pip 配置的 PyPI 索引安装。更新这两个客户端的版本后重新执行下载和安装两步。

1. 启动 MySQL 和 Redis。按 `back_end/saolei/saolei/settings.py` 的 `DATABASES` 配置创建数据库：开发默认数据库名为 `saolei`，用户名 `root`，密码 `123456`，地址 `127.0.0.1:3306`；Redis 默认地址为 `127.0.0.1:6379`，配置见 `CACHES`。

1. 在当前后端目录创建日志和资源目录：

   ```powershell
   New-Item -ItemType Directory -Force logs, assets
   ```

1. （可选，调试文章功能）在 `assets/` 下执行 `git clone https://gitee.com/ee55/saolei_website_article.git`，并将文件夹名由 `saolei_website_article` 改为 `article`。

1. 生成并应用数据库迁移：

   ```powershell
   .\.venv\Scripts\python.exe manage.py makemigrations
   .\.venv\Scripts\python.exe manage.py migrate userprofile
   .\.venv\Scripts\python.exe manage.py migrate
   ```

1. 启动开发后端：

   ```powershell
   .\.venv\Scripts\python.exe manage.py runserver --nostatic
   ```

1. （可选，调试定时任务）在另一个终端进入同一后端目录并运行：

   ```powershell
   .\.venv\Scripts\python.exe manage.py runapscheduler
   ```

前端（另开终端，回到项目根目录）：

1. 从[https://github.com/eee555/flop-player/releases/download/v1.1/dist.zip](https://github.com/eee555/flop-player/releases/download/v1.1/dist.zip)下载新版flop播放器，并解压到saolei_website\front_end\public\flop下（将文件夹的名称dist修改为flop），使得saolei_website\front_end\public\flop\index.html能够被找到
2. `cd front_end`
3. 如果使用npm，则npm install；如果知道什么是yarn且使用yarn，则yarn
4. 如果使用npm，则npm run dev；如果知道什么是yarn且使用yarn，则yarn dev
5. 如果使用npm且未部署后端，则`npm run frontend`，并且解除浏览器CORS，例如使用`CORS unblock`插件。

特殊的调试参数：位于`back_end\saolei\saolei\settings.py`的末尾。

### 生产端安装依赖

推送 tag 后，[网站部署 workflow](.github/workflows/build.yml)会在 GitHub runner 下载并校验两个客户端的 wheel，将 `wheels/` 随前端 `dist/` 上传到服务器后端目录，并在服务器校验 `wheels/SHA256SUMS`。[文档 workflow](.github/workflows/docs.yml)单独上传文档产物。上传步骤不安装依赖或重启服务。

更新服务器后端源码、确认上传完成后，在生产服务使用的 Python 环境中进入后端目录并校验：

```bash
cd /root/github/saolei_website/back_end/saolei
sha256sum -c wheels/SHA256SUMS
```

只有校验成功才继续。可以先预演，查看 `Would install` 中的依赖变更：

```bash
python3 -m pip install --dry-run --find-links wheels -r requirements.txt
```

正式安装时执行：

```bash
python3 -m pip install --find-links wheels -r requirements.txt
```

如果 `wheels/` 尚未准备好或需要重新下载，且生产端能够访问 GitHub Release，可在同一后端目录手动执行下载和安装：

```bash
python3 -m pip download --no-deps --dest wheels -r requirements-wheels.txt
python3 -m pip install --find-links wheels -r requirements.txt
```

下载步骤按清单中的固定 SHA-256 校验 wheel；安装步骤通过 `--find-links wheels` 查找本地包。两步都应使用生产服务所用的同一个 Python 解释器，示例为 `python3`。

生产端从本地 `wheels/` 获取两个客户端包，其余依赖继续使用服务器原有的 PyPI 索引（例如阿里云镜像）。安装后按现有部署流程应用迁移并重启后端。字段、导入流程和验证边界见 [WOM 接入说明](back_end/saolei/accountlink/wom/README.md)和 [MSGames 接入说明](back_end/saolei/accountlink/msgames/README.md)。

## 链接

网站链接：
- [开源扫雷网](https://openms.top)

相关项目主页：
- [元扫雷](https://github.com/eee555/Metasweeper)
- [ms-toollib综合工具箱](https://github.com/eee555/ms-toollib)
- [New Flop Player播放器](https://github.com/eee555/flop-player)

## 赞助
感谢您考虑支持我们的开源项目，赞助时请备注您的称呼和赞助的对象。赞助对象分为团队、网站运营、个人，如果没有备注，默认用于网站运营。您的赞助将有助于项目的持续发展和改进，使我们能够继续提高软件的质量。对团队整体的赞助，owner许诺向所有contributor按commit数量比例分配赞助得到的收入。

### 一般赞助者
- 累计捐款￥3及以上
- 您的名字将永久出现在项目的贡献者列表中（按照您要求的形式）
- 原则上不限次数的修改头像、个性签名的机会（需要联系管理员）
- 一对一的软件安装、网站使用指导

### 重要赞助者
- 累计捐款￥50及以上
- 一般赞助者的所有的权益
- 高度重视您提出的意见、优先修复您发现的bug
- 至少五倍的最大录像数量限制（需要联系管理员）

### 核心赞助者
- 累计捐款￥1000及以上
- 重要赞助者的所有的权益
- 可行的前提下，按照您的意见来制定开发计划

## 贡献者列表

| 赞助人 | 金额 | 时间 | 渠道 | 赞助对象 | 分配情况 |
| :------: | :-----:  | :----------: | :------: | :------:| :------: |
| *树             | ¥200.00 | 2026-10-26 | 微信 | 网站 | -- |
| 26225             | ¥200.00 | 2026-8-31 | 微信 | 网站 | -- |
| AUGUSTE             | ¥36.66 | 2026-7-21 | QQ | 网站 | -- |
| 毛毛虫             | ¥100.00 | 2026-7-21 | QQ | 网站 | -- |
| 用剑的人             | ¥1000.00 | 2025-11-18 | 微信 | 网站 | -- |
| 19003               | ¥100.00 | 2025-3-26 | 微信 | 网站 | -- |
| MsPVZ.ZSW           | ¥27.86  | 2024-12-3 | QQ | 网站 | -- |
| Codeine             | ¥10.00  | 2024-12-3 | QQ | 网站 | -- |
| putianyi889         | ¥200.00 | 2024-12-2 | 支付宝 | 网站 | -- |
| Ltabsyy             | ¥50.00  | 2024-12-2 | QQ | 网站 | -- |
| rhf                 | ¥13.14  | 2024-12-2 | QQ | 网站 | -- |
| 凌钦杰               | ¥8.00   | 2024-12-2 | QQ | 网站 | -- |
| 生命★是┗ 〓┛是☆什么 | ¥20.00  | 2024-12-2 | QQ | 网站 | -- |
| 柴油机               | ¥50.00  | 2024-12-2 | QQ | 网站 | -- |
| When                | ¥66.66  | 2024-12-2  | QQ | 网站 | -- |
| 问问好不好           | ¥16.66  | 2024-12-2  | QQ | 网站 | -- |
| putianyi889         | ¥100.00 | 2023-11-11 | 支付宝 | 网站 | -- |

## 网站运营支出

| 项目 | 金额 | 时间 | 品牌 | 备注 |
| :------: | :-----:  | :----------: | :----------: | :----------: |
| 域名        | ¥31.00 | 2026-5-25    | 西部数码 | openms.top |
| 预付费      | ¥50.00 | 2025-12-14 | 华为云 | 主要用于临时的服务器备份（当前剩余49.51元） |
| 服务器      | ¥1100.00 | 2025-11-18 | 华为云 | 华东-上海一 2核 2GiB 系统盘 40GiB 流量包 400GB 峰值带宽 3Mbit/s |
| 域名        | ¥31.00 | 2025-8-20    | 西部数码 | openms.top |
| 预付费 | ¥5.00 | 2025-4-16     | 百度 | 主要用于内容审核api |
| 服务器      | ¥429.14 | 2024-12-01  | 华为云 | 华东-上海一 2核 2GiB 系统盘 40GiB 流量包 400GB 峰值带宽 3Mbit/s |
| 域名        | ¥1.00  | 2024-8-25    | 西部数码 | openms.top |
| 域名        | ¥1.00  | 2023-12-11   | 华为云 | fff666.top |
| 服务器      | ¥89.14 | 2023-12-03   | 华为云 | 华东-上海一 2核 2GiB 系统盘 40GiB 流量包 400GB 峰值带宽 3Mbit/s |

当前账户余额：￥461.18

资源到期时间和下期金额：

| 项目 | 时间 | 金额 |
| :------: | :-----:  | :----------: |
| 域名      | 2027.8.25 | ￥31.00 |
| 服务器    | 2027.12.02 | ￥550.00 |


![](readme_pic/微信收款码.png) ![](readme_pic/支付宝收款码.png)  

