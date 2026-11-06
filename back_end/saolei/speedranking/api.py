from ninja import Router

from .pb.api import router as pb_router
from .saolei.api import router as saolei_router
from .strict_ng.api import router as strict_ng_router
from .top.api import router as top_router

router = Router()
router.add_router('', saolei_router)
router.add_router('/strict_ng', strict_ng_router)
router.add_router('/pb', pb_router)
router.add_router('/top', top_router)
