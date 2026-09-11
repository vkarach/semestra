from aiogram import Router

from .common import router as common_router
from .upload import router as upload_router
from .schedule import router as schedule_router
from .admin import router as admin_router

router = Router()
router.include_router(common_router)
router.include_router(upload_router)
router.include_router(schedule_router)
router.include_router(admin_router)
