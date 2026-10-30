import os

from django.conf import settings
from django_redis import get_redis_connection

cache = get_redis_connection('saolei_website')


def refresh_article_list():
    article_dir = settings.BASE_DIR / 'assets' / 'article' if settings.DEBUG else os.path.join(settings.STATIC_ROOT, 'article')
    articles = os.listdir(article_dir)
    names = []
    for article in articles:
        if os.path.isdir(os.path.join(article_dir, article)):
            if os.path.isfile(os.path.join(article_dir, article, 'a.md')):
                names.append(article)
        elif article.endswith('.md') and article.startswith('['):
            names.append(article)
    with cache.pipeline(transaction=True) as pipe:
        pipe.delete('articles')
        if names:
            pipe.lpush('articles', *names)
        pipe.execute()
    return len(names)
