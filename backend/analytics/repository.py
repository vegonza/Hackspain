from analytics.models import AnalyticsOverview
from shared.storage import get_client


def analytics_overview() -> AnalyticsOverview:
    payload = get_client().rpc("get_analytics_dashboard", {}).execute().data
    return AnalyticsOverview.model_validate(payload)
