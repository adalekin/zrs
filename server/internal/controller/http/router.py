from fastapi import APIRouter

from internal.controller.http import health
from internal.controller.http.v1 import people, reference_items, requests

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(people.router)
v1_router.include_router(reference_items.router)
v1_router.include_router(requests.router)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(v1_router)
