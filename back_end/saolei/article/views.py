from django.http import HttpResponse, JsonResponse
from django_redis import get_redis_connection

cache = get_redis_connection('saolei_website')

# 用文件系统管理文章
# 定时整理文章的目录文件，删除目录里没有文件的目录、添加不在目录里的文章
# 文章可以是文件夹或文件
# 任意图片png、jpg封面和md正文


# 完整文章目录
def article_list(request):
    if request.method == 'GET':
        a_list = cache.lrange('articles', 0, -1)
        # 不做过多处理（排序、分类）直接发到前端
        return JsonResponse([a.decode('utf-8') for a in a_list], safe=False)
    else:
        return HttpResponse('别瞎玩')
