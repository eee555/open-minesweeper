#!/bin/bash
rm -rf /root/saolei/static
# 搜集静态文件到/root/saolei/static，按照setting的配置，只有dist
echo "开始搜集静态文件，大约20秒..."
python3 manage.py collectstatic --noinput
echo "静态文件搜集完成。"
# 前端文件的打包结果来自github工作流
python3 manage.py makemigrations
python3 manage.py migrate

mkdir -p logs

if [ "${START_APSCHEDULER:-1}" = "1" ]; then
    echo "Starting apscheduler after ${APSCHEDULER_START_DELAY:-10}s..."
    nohup bash run_background.sh apscheduler "${APSCHEDULER_START_DELAY:-10}" "${APSCHEDULER_NICE:-10}" \
        >> logs/apscheduler.log 2>&1 < /dev/null &
    echo "apscheduler scheduled."
else
    echo "Skipping apscheduler because START_APSCHEDULER=${START_APSCHEDULER}."
fi

if [ "${START_DB_WORKER:-1}" = "1" ]; then
    echo "Starting db_worker after ${DB_WORKER_START_DELAY:-20}s..."
    nohup bash run_background.sh db-worker "${DB_WORKER_START_DELAY:-20}" "${DB_WORKER_NICE:-10}" "${DB_WORKER_INTERVAL:-2}" \
        >> logs/db_worker.log 2>&1 < /dev/null &
    echo "db_worker scheduled."
else
    echo "Skipping db_worker because START_DB_WORKER=${START_DB_WORKER}."
fi

cp -f default.conf /etc/nginx/conf.d/default.conf
sudo nginx -s reload
uwsgi --ini uwsgi.ini
