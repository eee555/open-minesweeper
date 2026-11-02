"""隔离原生录像解析的内部进程入口，不加载 Django 应用或访问数据库。"""

import json
import os
from pathlib import Path
import sys

from django.core.files.base import ContentFile

from .exceptions import ExceptionToResponse
from .parser import MSVideoParser

if os.name == 'posix':
    import resource


def main():
    if os.name == 'posix':
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    suffix, result_path = sys.argv[1:]
    try:
        parser = MSVideoParser(ContentFile(sys.stdin.buffer.read(), name=f'replay{suffix}'))
    except ExceptionToResponse as exc:
        payload = {'error': {'obj': exc.obj, 'category': exc.category, 'status_code': exc.status_code}}
    except BaseException as exc:
        if exc.__class__.__name__ != 'PanicException':
            raise
        payload = {'error': {'obj': 'rust', 'category': 'panic', 'status_code': 500}}
    else:
        metadata = {key: value for key, value in vars(parser).items() if key != 'file'}
        metadata['end_time'] = metadata['end_time'].isoformat()
        payload = {'metadata': metadata}
    # 原生库可能向 stdout 输出诊断；结果使用独立文件，避免污染 JSON。
    Path(result_path).write_text(json.dumps(payload), encoding='utf-8')


if __name__ == '__main__':
    main()
