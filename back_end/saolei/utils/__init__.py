import base64
from datetime import date, datetime
from decimal import Decimal
import json
import random

from django.conf import settings
import requests

from .exceptions import ExceptionToResponse
from .secrets_json import read_secret, write_secret


def generate_code(code_len):
    """
    生成指定长度的验证码
    :param code_len: 验证码长度（4-6位）
    :return: 生成的验证码
    """
    all_chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    code = ''
    for _ in range(code_len):
        index = random.randint(0, len(all_chars) - 1)
        code += all_chars[index]
    return code

# https://zhuanlan.zhihu.com/p/429228350
# def active_user(request, active_code):
#     """查询验证码"""
#     all_records = EmailVerifyRecord.objects.filter(code=active_code)
#     if all_records:
#         for record in all_records:
#             email = record.email
#             user = User.objects.get(email=email)
#             user.is_staff = True
#             user.save()
#     else:
#         return HttpResponse('链接有误！')
#     return redirect('users:login')


class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%dT%H:%M:%SZ')
        elif isinstance(obj, date):
            return obj.strftime('%Y-%m-%d')
        elif isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, bytes):
            return str(obj, encoding='utf-8')
        else:
            return json.JSONEncoder.default(self, obj)


def get_access_token() -> str:
    """
    使用 AK，SK 生成鉴权签名（Access Token）。不能调用太多次。
    :return: access_token，或是None(如果错误)
    """
    try:
        API_KEY = str(read_secret('client_id'))
    except Exception:
        API_KEY = input('请输入client_id：')
    try:
        SECRET_KEY = str(read_secret('client_secret'))
    except Exception:
        SECRET_KEY = input('请输入client_secret：')
    url = 'https://aip.baidubce.com/oauth/2.0/token'
    params = {'grant_type': 'client_credentials', 'client_id': API_KEY, 'client_secret': SECRET_KEY}
    token = str(requests.post(url, params=params, timeout=5).json().get('access_token'))
    write_secret('token', token)

    if token == 'None':
        return '**********************************************\n\n**  警告！内容审核的鉴权签名获取失败！！！  **\n\n**********************************************'
    return token


def get_ACCESS_TOKEN() -> str:
    try:
        return str(read_secret('token'))
    except KeyError:
        return get_access_token()
    except FileNotFoundError:
        raise ExceptionToResponse(obj='baidu', category='fileNotFound')
    except json.JSONDecodeError:
        raise ExceptionToResponse(obj='baidu', category='jsonDecode')
    except Exception:
        raise ExceptionToResponse(obj='baidu', category='unknown')


# 百度大脑鉴别文本合规性
def verify_text(text: str, user_id: int = 0, user_ip: str = '192.168.0.1') -> bool:
    if settings.BAIDU_VERIFY_SKIP:
        return True
    if not text:
        return True
    url = 'https://aip.baidubce.com/rest/2.0/solution/v1/text_censor/v2/user_defined?access_token=' + get_ACCESS_TOKEN()
    payload = {
        'text': text,
        'userId': str(user_id),
        'userIp': user_ip,
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    }
    response = requests.request('POST', url, headers=headers, data=payload, timeout=5)
    response.raise_for_status()
    result = response.json()
    if result.get('error_code') == 111:
        # token过期了
        url = 'https://aip.baidubce.com/rest/2.0/solution/v1/text_censor/v2/user_defined?access_token=' + get_access_token()
        response = requests.request('POST', url, headers=headers, data=payload, timeout=5)
        response.raise_for_status()
        result = response.json()
    conclusion = result.get('conclusion')
    if result.get('error_code') or conclusion not in ('合规', '不合规', '疑似'):
        raise ValueError('Text moderation did not return a verdict')
    return conclusion == '合规'


# 百度大脑鉴别图片合规性
# 百度api对图片的尺寸、大小都有要求，后期再测试、适配
def verify_image(image_binary, user_id: int, user_ip: str) -> bool:
    if settings.BAIDU_VERIFY_SKIP:
        return True
    if not image_binary:
        return True
    image_base64 = base64.b64encode(image_binary).decode()
    url = 'https://aip.baidubce.com/rest/2.0/solution/v1/img_censor/v2/user_defined?access_token=' + get_ACCESS_TOKEN()
    payload = {
        'image': image_base64,
        'user_id': user_id,
        'user_ip': user_ip,
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    }
    response = requests.request('POST', url, headers=headers, data=payload)
    if response.json().get('error_code') == 111:
        # token过期了
        url = 'https://aip.baidubce.com/rest/2.0/solution/v1/img_censor/v2/user_defined?access_token=' + get_access_token()
        response = requests.request('POST', url, headers=headers, data=payload)
    return response.json().get('conclusion') == '合规'
