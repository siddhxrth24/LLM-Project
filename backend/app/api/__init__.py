from app.api.courses import router as courses_router
from app.api.documents import router as documents_router
from app.api.schedule import router as schedule_router
from app.api.settings import router as settings_router
from app.api.syllabus import router as syllabus_router
from app.api.topics import router as topics_router

__all__ = [
    "courses_router",
    "documents_router",
    "syllabus_router",
    "schedule_router",
    "topics_router",
    "settings_router",
]
