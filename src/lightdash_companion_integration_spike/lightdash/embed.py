import json
import time
import urllib.parse
from collections.abc import Mapping

import jwt

EMBED_TOKEN_LIFETIME_SECONDS = 3600


def build_jwt_payload(
    *,
    project_uuid: str,
    user_attributes: Mapping[str, str],
    now: int,
) -> dict[str, object]:
    """
    Build the claims for an embed token that allows exploring.

    `metricsCatalog` is the content type that grants `canExplore` without needing a saved
    dashboard or chart, which an unsaved chat query does not have.
    """
    return {
        "content": {
            "type": "metricsCatalog",
            "projectUuid": project_uuid,
            "canExplore": True,
        },
        "userAttributes": dict(user_attributes),
        "iat": now,
        "exp": now + EMBED_TOKEN_LIFETIME_SECONDS,
    }


def mint_token(*, secret: str, payload: Mapping[str, object]) -> str:
    return jwt.encode(dict(payload), secret, algorithm="HS256")


def build_explore_url(
    *,
    site_url: str,
    project_uuid: str,
    explore_name: str,
    saved_chart_version: Mapping[str, object],
    token: str,
) -> str:
    query = urllib.parse.urlencode(
        {"create_saved_chart_version": json.dumps(saved_chart_version)}
    )
    base = f"{site_url.rstrip('/')}/embed/{project_uuid}/explore/{explore_name}"
    return f"{base}?{query}#{token}"


def now_seconds() -> int:
    return int(time.time())


def explore_state(
    *, explore_name: str, query_config: Mapping[str, object], column_order: list[str]
) -> dict[str, object]:
    """
    Build the `create_saved_chart_version` payload the embedded explore loads.

    This mirrors what Lightdash puts in the `exploreUrl` share link, minus the chart config,
    so the explore opens on the table view of the same query.
    """
    return {
        "tableName": explore_name,
        "metricQuery": {
            "exploreName": explore_name,
            "dimensions": query_config.get("dimensions", []),
            "metrics": query_config.get("metrics", []),
            "filters": {},
            "sorts": query_config.get("sorts", []),
            "limit": query_config.get("limit") or 500,
            "tableCalculations": [],
        },
        "tableConfig": {"columnOrder": column_order},
        "chartConfig": {"type": "table"},
    }
