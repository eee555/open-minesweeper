# <a href="https://github.com/eee555/saolei_website" >Open Minesweeper (开源扫雷网)</a>

[![saolei_website](https://img.shields.io/badge/saolei_website-v1.7-brightgreen.svg)](https://github.com/eee555/Solvable-Minesweeper)
[![stars](https://img.shields.io/github/stars/eee555/saolei_website)](https://github.com/eee555/saolei_website/stargazers)
[![forks](https://img.shields.io/github/forks/eee555/saolei_website)](https://github.com/eee555/saolei_website/forks)

[![Dependabot Updates](https://github.com/eee555/saolei_website/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/eee555/saolei_website/actions/workflows/dependabot/dependabot-updates)

[中文](README.md)

Open Minesweeper (开源扫雷网) was founded on December 3, 2023. It is a non-profit replay ranking platform voluntarily maintained by veteran Minesweeper players. Players upload Minesweeper replays, and the system automatically parses them and generates speed rankings, supporting Standard, Blind, No Guess, Density, PB and other leaderboards, while also providing tournament services such as the Golden Sheep Cup (GSC) and weekly contests. Compared with traditional centralized websites, Open Minesweeper upholds the core idea of being community-driven: what it builds is an open collaborative ecosystem. Developers, sponsors, tournament organizers, and every user are welcome to join.

**Community-driven, democratically governed.** Unlike traditional centralized websites, every decision of this project—including feature direction and the choice of site owner and administrators—can in principle be decided by a vote of the core team.

We believe in the power of the Minesweeper community. Whether you are a developer, a tournament organizer, a content creator, or just a player, there is a place for you here. To join us, see "Contact Us" at the bottom of the [website](https://openms.top).

> **Frontend**: Vue 3 + TypeScript + Vite + Element Plus + PrimeVue + Tailwind CSS + WASM  
> **Backend**: Django + django-ninja + MySQL + Redis  
> **Replay parsing**: ms-toollib (Rust-compiled WASM / Python library)  
> **Deployment**: Nginx + uWSGI + acme.sh  
> **Content moderation**: Baidu Brain  
> **License**: MIT License

To run everything locally you need to start the backend, the frontend, and the medal worker at the same time. Test accounts and addresses are in [本地启动.md](本地启动.md).

## Setup steps:

This project can be developed on Windows and deployed on Linux. Install Python, Node.js, MySQL, and Redis, then clone the repository. The development commands below use Windows PowerShell and start at the repository root.

Backend:

1. Enter the backend directory and create a virtual environment; if `.venv` already exists, there is no need to recreate it:

   ```powershell
   cd back_end\saolei
   python -m venv .venv
   ```

1. Download the release wheels first, then install dependencies. `requirements-wheels.txt` pins the GitHub release URL and SHA-256 hash of `msgames-api`; `requirements.txt` pins the installed versions. The `wheels/` directory is not committed to Git:

   ```powershell
   .\.venv\Scripts\python.exe -m pip download --no-deps --dest wheels -r requirements-wheels.txt
   .\.venv\Scripts\python.exe -m pip install --find-links wheels -r requirements.txt
   ```

   The development machine needs GitHub access to download these wheels; other dependencies use the PyPI index configured for pip. Repeat the download and install steps after updating either client version.

1. Start MySQL and Redis. Create the database according to `DATABASES` in `back_end/saolei/saolei/settings.py`: the development defaults are database `saolei`, user `root`, password `123456`, and address `127.0.0.1:3306`. Redis defaults to `127.0.0.1:6379`; see `CACHES` for its configuration.

1. Create the log and asset directories in the current backend directory:

   ```powershell
   New-Item -ItemType Directory -Force logs, assets
   ```

1. (Optional, for testing the article feature) In `assets/`, run `git clone https://gitee.com/ee55/saolei_website_article.git` and rename the folder `saolei_website_article` to `article`.

1. Generate and apply database migrations:

   ```powershell
   .\.venv\Scripts\python.exe manage.py makemigrations
   .\.venv\Scripts\python.exe manage.py migrate userprofile
   .\.venv\Scripts\python.exe manage.py migrate
   ```

1. Start the development backend:

   ```powershell
   .\.venv\Scripts\python.exe manage.py runserver --nostatic
   ```

1. (Optional, for testing scheduled tasks) In another terminal, enter the same backend directory and run:

   ```powershell
   .\.venv\Scripts\python.exe manage.py runapscheduler
   ```

Frontend (open another terminal and return to the repository root):

1. Download the latest flop player from [https://github.com/eee555/flop-player/releases/download/v1.1/dist.zip](https://github.com/eee555/flop-player/releases/download/v1.1/dist.zip) and unzip it to `saolei_website\front_end\public\flop` (rename the folder `dist` to `flop`), so that `saolei_website\front_end\public\flop\index.html` can be found.
2. `cd front_end`
3. If you use npm, run `npm install`; if you know what yarn is and use yarn, run `yarn`.
4. If you use npm, run `npm run dev`; if you know what yarn is and use yarn, run `yarn dev`.
5. If you use npm and the backend is not deployed, run `npm run frontend` and unblock CORS in the browser, for example with the "CORS unblock" extension.

Special debugging parameters are located at the end of `back_end\saolei\saolei\settings.py`.

### Installing production dependencies

On a tag push, the [website deployment workflow](.github/workflows/build.yml) downloads and verifies both client wheels on the GitHub runner, uploads `wheels/` together with the frontend `dist/` to the server's backend directory, and verifies `wheels/SHA256SUMS` on the server. The [documentation workflow](.github/workflows/docs.yml) uploads documentation artifacts separately. The upload step does not install dependencies or restart services.

After updating the server's backend source and confirming the upload has completed, enter the backend directory in the Python environment used by the production service and verify:

```bash
cd /root/github/saolei_website/back_end/saolei
sha256sum -c wheels/SHA256SUMS
```

Continue only if verification succeeds. You can first do a dry run to see the dependency changes listed under `Would install`:

```bash
python3 -m pip install --dry-run --find-links wheels -r requirements.txt
```

For the actual installation, run:

```bash
python3 -m pip install --find-links wheels -r requirements.txt
```

If `wheels/` is not ready yet or needs to be downloaded again, and production can access GitHub Releases, you can run the download and install steps manually from the same backend directory:

```bash
python3 -m pip download --no-deps --dest wheels -r requirements-wheels.txt
python3 -m pip install --find-links wheels -r requirements.txt
```

The download step verifies each wheel against the SHA-256 pinned in the manifest; the install step discovers the local packages through `--find-links wheels`. Both steps should use the same Python interpreter as the production service; the examples use `python3`.

Production obtains both client packages from the local `wheels/` directory, while other dependencies continue to use the server's existing PyPI index (for example the Aliyun mirror). After installation, apply migrations and restart the backend following the existing deployment procedure. See the [WOM integration notes](back_end/saolei/accountlink/wom/README.md) and [MSGames integration notes](back_end/saolei/accountlink/msgames/README.md) for the fields, import workflow, and validation limits.

## Links

Website:
- [Open Minesweeper](https://openms.top)

Related projects:
- [Metasweeper](https://github.com/eee555/Metasweeper)
- [ms-toollib toolbox](https://github.com/eee555/ms-toollib)
- [New Flop Player](https://github.com/eee555/flop-player)

## Sponsorship
Thank you for considering supporting our open-source project. When sponsoring, please note your name and the sponsorship target. Targets are the team, website operations, or an individual; if no note is given, the donation is used for website operations by default. Your sponsorship helps the project continue to develop and improve, allowing us to keep raising the quality of the software. For team-level sponsorship, the owner promises to distribute the resulting income to all contributors in proportion to their commit counts.

### General sponsor
- Cumulative donation of ¥3 or more
- Your name will appear permanently in the project's contributor list (in the form you request)
- In principle, unlimited changes to your avatar and signature (contact an administrator)
- One-on-one guidance for software installation and website usage

### Important sponsor
- Cumulative donation of ¥50 or more
- All benefits of a general sponsor
- Your opinions are highly valued, and bugs you report are fixed with priority
- At least five times the maximum replay count limit (contact an administrator)

### Core sponsor
- Cumulative donation of ¥1000 or more
- All benefits of an important sponsor
- Where feasible, development plans are made according to your suggestions

## Contributor list

| Sponsor | Amount | Date | Channel | Target | Allocation |
| :------: | :-----:  | :----------: | :------: | :------:| :------: |
| xiean             | ¥99.00 | 2026-11-5 | QQ | Website | -- |
| 18875             | ¥63.00 | 2026-10-31 | Alipay | Website | -- |
| Vostok             | ¥5.00 | 2026-10-31 | WeChat | Website | -- |
| *树             | ¥200.00 | 2026-10-26 | WeChat | Website | -- |
| 26225             | ¥200.00 | 2026-8-31 | WeChat | Website | -- |
| AUGUSTE             | ¥36.66 | 2026-7-21 | QQ | Website | -- |
| 毛毛虫             | ¥100.00 | 2026-7-21 | QQ | Website | -- |
| 用剑的人             | ¥1000.00 | 2025-11-18 | WeChat | Website | -- |
| 19003               | ¥100.00 | 2025-3-26 | WeChat | Website | -- |
| MsPVZ.ZSW           | ¥27.86  | 2024-12-3 | QQ | Website | -- |
| Codeine             | ¥10.00  | 2024-12-3 | QQ | Website | -- |
| putianyi889         | ¥200.00 | 2024-12-2 | Alipay | Website | -- |
| Ltabsyy             | ¥50.00  | 2024-12-2 | QQ | Website | -- |
| rhf                 | ¥13.14  | 2024-12-2 | QQ | Website | -- |
| 凌钦杰               | ¥8.00   | 2024-12-2 | QQ | Website | -- |
| 生命★是┗ 〓┛是☆什么 | ¥20.00  | 2024-12-2 | QQ | Website | -- |
| 柴油机               | ¥50.00  | 2024-12-2 | QQ | Website | -- |
| When                | ¥66.66  | 2024-12-2  | QQ | Website | -- |
| 问问好不好           | ¥16.66  | 2024-12-2  | QQ | Website | -- |
| putianyi889         | ¥100.00 | 2023-11-11 | Alipay | Website | -- |

## Website operating expenses

| Item | Amount | Date | Vendor | Notes |
| :------: | :-----:  | :----------: | :----------: | :----------: |
| Domain        | ¥31.00 | 2026-5-25    | West.cn | openms.top |
| Prepaid      | ¥50.00 | 2025-12-14 | Huawei Cloud | Mainly for temporary server backups (¥49.51 currently remaining) |
| Server      | ¥1100.00 | 2025-11-18 | Huawei Cloud | East China - Shanghai 1, 2 cores, 2 GiB, 40 GiB system disk, 400 GB traffic package, 3 Mbit/s peak bandwidth |
| Domain        | ¥31.00 | 2025-8-20    | West.cn | openms.top |
| Prepaid | ¥5.00 | 2025-4-16     | Baidu | Mainly used for the content moderation API |
| Server      | ¥429.14 | 2024-12-01  | Huawei Cloud | East China - Shanghai 1, 2 cores, 2 GiB, 40 GiB system disk, 400 GB traffic package, 3 Mbit/s peak bandwidth |
| Domain        | ¥1.00  | 2024-8-25    | West.cn | openms.top |
| Domain        | ¥1.00  | 2023-12-11   | Huawei Cloud | fff666.top |
| Server      | ¥89.14 | 2023-12-03   | Huawei Cloud | East China - Shanghai 1, 2 cores, 2 GiB, 40 GiB system disk, 400 GB traffic package, 3 Mbit/s peak bandwidth |

Current account balance: ¥628.18

Resource expiry dates and next payment amounts:

| Item | Date | Amount |
| :------: | :-----:  | :----------: |
| Domain      | 2027.8.25 | ¥31.00 |
| Server    | 2027.12.02 | ¥550.00 |


![](readme_pic/微信收款码.png) ![](readme_pic/支付宝收款码.png)  
