from django.http import JsonResponse
from ninja import NinjaAPI, Redoc

from accountlink.api import router as accountlink_router
from accountlink.discord.api import router as accountlink_discord_router
from accountlink.msgames.api import router as accountlink_msgames_router
from article.api import router as article_router
from common.api import router as common_router
from customranking.api import router as customranking_router
from effranking.api import router as effranking_router
from identifier.api import router as identifier_router
from medal.api import router as medal_router
from minigame.api import router as minigame_router
from minigame.utils import MiniGameError
from monitor.api import router as monitor_router
from msuser.api import router as msuser_router
from speedranking.api import router as speedranking_router
from tournament.api import router as tournament_router
from tournament.gsc.api import router as tournament_gsc_router
from tournament.weekly.api import router as tournament_weekly_router
from userprofile.api import router as userprofile_router
from utils.exceptions import ExceptionToResponse
from videomanager.api import router as videomanager_router

api = NinjaAPI(docs=Redoc())

api.add_router('/common/', common_router)
api.add_router('/monitor/', monitor_router)
api.add_router('/userprofile/', userprofile_router)
api.add_router('/accountlink/', accountlink_router)
api.add_router('/accountlink/discord/', accountlink_discord_router)
api.add_router('/accountlink/msgames/', accountlink_msgames_router)
api.add_router('/article/', article_router)
api.add_router('/video/', videomanager_router)
api.add_router('/customranking/', customranking_router)
api.add_router('/identifier/', identifier_router)
api.add_router('/medal/', medal_router)
api.add_router('/msuser/', msuser_router)
api.add_router('/speedranking/', speedranking_router)
api.add_router('/effranking/', effranking_router)
api.add_router('/minigame/', minigame_router)
api.add_router('/tournament/', tournament_router)
api.add_router('/tournament/gsc/', tournament_gsc_router)
api.add_router('/tournament/weekly/', tournament_weekly_router)


@api.exception_handler(ExceptionToResponse)
def general_exception(request, exc: ExceptionToResponse):
    return exc.response()


@api.exception_handler(MiniGameError)
def minigame_exception(request, exc: MiniGameError):
    return JsonResponse({'code': exc.code, 'detail': exc.detail}, status=exc.status)
