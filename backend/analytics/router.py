from fastapi import APIRouter

from analytics.models import AnalyticsOverview
from analytics.repository import analytics_overview

router = APIRouter(prefix="/api/analytics")


@router.get("")
def get_analytics() -> AnalyticsOverview:
    return analytics_overview()
