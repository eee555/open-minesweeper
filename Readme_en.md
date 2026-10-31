# <a href="https://github.com/eee555/saolei_website" >开源扫雷网（Open Minesweeper）</a>


[![saolei_website](https://img.shields.io/badge/saolei_website-v1.7-brightgreen.svg)](https://github.com/eee555/Solvable-Minesweeper)
[![stars](https://img.shields.io/github/stars/eee555/saolei_website)](https://github.com/eee555/saolei_website/stargazers)
[![forks](https://img.shields.io/github/forks/eee555/saolei_website)](https://github.com/eee555/saolei_website/forks)


Front end：Vue3 + Ts + Element-ui + wasm-bindgen  
Back end：Django + Mysql + redis  
Deployment：Nginx + uwsgi  
Censorship：百度大脑  


To run the local site, start the backend, frontend, and medal worker. Accounts and URLs are in [本地启动.md](本地启动.md).

## Steps for deployment：

This project can be developed on Windows and deployed on Linux. Install Python, Node.js, MySQL, and Redis, then clone the repository. The development commands below use Windows PowerShell and start at the repository root.

Back end:

1. Enter the backend directory and create a virtual environment. Skip creation if `.venv` already exists:

   ```powershell
   cd back_end\saolei
   python -m venv .venv
   ```

1. Download the release wheels, then install dependencies. `requirements-wheels.txt` pins the GitHub release URL and SHA-256 hash of `msgames-api`; `requirements.txt` pins the installed versions. The `wheels/` directory is ignored by Git:

   ```powershell
   .\.venv\Scripts\python.exe -m pip download --no-deps --dest wheels -r requirements-wheels.txt
   .\.venv\Scripts\python.exe -m pip install --find-links wheels -r requirements.txt
   ```

   The development machine needs GitHub access to download these wheels. Other dependencies use your configured PyPI index. Repeat both commands when updating either client version.

1. Start MySQL and Redis. Create the database according to `DATABASES` in `back_end/saolei/saolei/settings.py`: development defaults are database `saolei`, user `root`, password `123456`, and address `127.0.0.1:3306`. Redis defaults to `127.0.0.1:6379`; see `CACHES` for its configuration.

1. Create the log and asset directories in the current backend directory:

   ```powershell
   New-Item -ItemType Directory -Force logs, assets
   ```

1. To test articles, run `git clone https://gitee.com/ee55/saolei_website_article.git` in `assets/` and rename the folder `saolei_website_article` to `article`.

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

1. To test scheduled tasks, open another terminal in the same backend directory and run:

   ```powershell
   .\.venv\Scripts\python.exe manage.py runapscheduler
   ```

Front end (open another terminal at the repository root):

1. Download the latest flop player from [https://github.com/eee555/flop-player/releases/download/v1.1/dist.zip](https://github.com/eee555/flop-player/releases/download/v1.1/dist.zip) and unzip it to `saolei_website\front_end\public\flop` (rename the folder name `dist` to `flop`), such that `saolei_website\front_end\public\flop\index.html` is accessible.
1. `cd front_end`
1. `npm install`
1. `npm run dev` to test front-end with local back-end.
2. `npm run frontend` to test front-end with remote back-end. CORS from the browser has to be unblocked. It is recommended to use the "CORS unblock" Chrome extension.

Special debugging parameters are located at the end of `back_end\saolei\saolei\settings.py`

### Installing production dependencies

On a tag push, the [website deployment workflow](.github/workflows/build.yml) downloads and verifies both client wheels on the GitHub runner, uploads `wheels/` alongside the frontend `dist/` to the server's backend directory, and verifies `wheels/SHA256SUMS` on the server. The [documentation workflow](.github/workflows/docs.yml) uploads documentation separately. Uploading does not install dependencies or restart services.

After updating the backend source and confirming the upload has completed, use the production service's Python environment to verify the files:

```bash
cd /root/github/saolei_website/back_end/saolei
sha256sum -c wheels/SHA256SUMS
```

Continue only if verification succeeds. Preview dependency changes with:

```bash
python3 -m pip install --dry-run --find-links wheels -r requirements.txt
```

For the actual installation, run:

```bash
python3 -m pip install --find-links wheels -r requirements.txt
```

If `wheels/` is not ready or needs to be downloaded again, and production can access GitHub Releases, run both steps manually from the same backend directory:

```bash
python3 -m pip download --no-deps --dest wheels -r requirements-wheels.txt
python3 -m pip install --find-links wheels -r requirements.txt
```

The download step checks each wheel against the SHA-256 pinned in the manifest; installation discovers the local packages through `--find-links wheels`. Use the same Python interpreter as the production service for both steps; these examples use `python3`.

Production obtains both client packages from the local `wheels/` directory. Other dependencies continue to use the server's configured PyPI index, such as the Aliyun mirror. Apply migrations and restart the backend using your existing deployment procedure. See the [WOM integration notes](back_end/saolei/accountlink/wom/README.md) and [MSGames integration notes](back_end/saolei/accountlink/msgames/README.md) for the fields, import workflow, and validation limits.

## Sponsor
TODO
