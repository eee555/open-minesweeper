from saolei_api import Client

from utils.secrets_json import read_secret


def saolei_client():
    """一次命令共用一个客户端；密钥只在实际同步时读取。"""
    return Client(read_secret('saolei_api_key'), timeout=30, min_interval=2.1, download_interval=0.4)
