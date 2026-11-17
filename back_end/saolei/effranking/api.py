from ninja import Router

from .nf_ioe.api import router as nf_ioe_router
from .thrp.api import router as thrp_router
from .tpe.api import router as tpe_router

router = Router()
router.add_router('/thrp', thrp_router)
router.add_router('/nf_ioe', nf_ioe_router)
router.add_router('/tpe', tpe_router)
