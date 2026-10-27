from fastapi import APIRouter

from backend.modules.student_life import router as student_life_router
from backend.routers.academics import router as academics_router
from backend.routers.campus_life import router as campus_life_router
from backend.routers.community_resources import router as community_resources_router
from backend.routers.facilities import router as facilities_router
from backend.routers.governance_careers import router as governance_careers_router
from backend.routers.hardware_os import router as hardware_os_router
from backend.routers.operations import router as operations_router
from backend.routers.operational_tools import router as operational_tools_router
from backend.routers.student_services import router as student_services_router
from backend.routers.stakeholders import router as stakeholders_router

router = APIRouter(prefix="/api/v1")
router.include_router(academics_router)
router.include_router(campus_life_router)
router.include_router(community_resources_router)
router.include_router(facilities_router)
router.include_router(governance_careers_router)
router.include_router(hardware_os_router)
router.include_router(student_services_router)
router.include_router(stakeholders_router)
router.include_router(operations_router)
router.include_router(operational_tools_router)
router.include_router(student_life_router)