from aiogram import Router

from bot.keyboards import PromptCb
from bot.middlewares import ResetStateMiddleware
from .common import router as common_router
from .upload import router as upload_router, Upload
from .schedule import router as schedule_router
from .prompts import router as prompts_router, Prompt
from .events import router as events_router
from .subjects import router as subjects_router
from .settings import router as settings_router
from .help import router as help_router
from .admin import router as admin_router

reset_state = ResetStateMiddleware(callback_owners={
    Upload.__name__: "import:",
    Prompt.__name__: f"{PromptCb.__prefix__}:",
})

router = Router()
router.message.outer_middleware(reset_state)
router.callback_query.outer_middleware(reset_state)
router.include_router(common_router)
router.include_router(upload_router)
router.include_router(schedule_router)
router.include_router(prompts_router)
router.include_router(events_router)
router.include_router(subjects_router)
router.include_router(settings_router)
router.include_router(help_router)
router.include_router(admin_router)
