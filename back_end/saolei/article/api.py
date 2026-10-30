from ninja import Router
from ninja.security.session import SessionAuthIsStaff

from .services import refresh_article_list

router = Router()


@router.post('/admin/refresh', auth=SessionAuthIsStaff(), response=int)
def refresh_articles(request):
    """- auth=SessionAuthIsStaff (staff or superuser, Django session and CSRF)"""
    return refresh_article_list()
