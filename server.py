"""Your MCP server for San Francisco 311 data.

FastMCP Gateway runs this file. Its entrypoint setting is `server.py:mcp`.
"""

import logging
import re
from collections import Counter, defaultdict
from statistics import median
from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from sf311.data import BY_ID, LOCAL_NAMES, NEIGHBORHOODS, REQUESTS, SERVICES, Request, closest
from sf311.kit import caller_email

mcp = FastMCP("sf-311")

logger = logging.getLogger(__name__)

READ_ONLY = {"readOnlyHint": True}
MAX_ROWS = 50
HOUSE_NUMBER = re.compile(r"^(\d+)\s+([^,]+)")
GROUPS = {
    "neighborhood": lambda r: r.neighborhood,
    "service": lambda r: r.service,
    "agency": lambda r: r.agency,
    "source": lambda r: r.source,
    "weekday": lambda r: r.opened.strftime("%A"),
    "status": lambda r: r.status,
}


def _check(name: str | None, valid: list[str], kind: str) -> None:
    if name is not None and name not in valid:
        suggestions = ", ".join(closest(name, valid)) or "call dataset_info for the full list"
        raise ToolError(f"Unknown {kind} {name!r}. Did you mean: {suggestions}?")


def _matching(service: str | None, neighborhood: str | None, status: str | None = None) -> list[Request]:
    _check(service, SERVICES, "service")
    _check(neighborhood, NEIGHBORHOODS, "neighborhood")
    return [
        r
        for r in REQUESTS
        if (service is None or r.service == service)
        and (neighborhood is None or r.neighborhood == neighborhood)
        and (status is None or r.status == status)
    ]


def _ranked(counter: Counter) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:MAX_ROWS])


def _masked(request: Request) -> dict:
    """request.as_dict(), with the street address rounded down to its block.

    "994 HARRISON ST, SAN FRANCISCO, CA 94107, US" becomes "900 block of
    HARRISON ST". An address with no house number, such as an intersection,
    is left as it is.
    """
    row = request.as_dict()
    match = HOUSE_NUMBER.match(row["address"])
    if match:
        block = int(match.group(1)) // 100 * 100
        row["address"] = f"{block} block of {match.group(2).strip()}"
    return row


@mcp.resource("resource://dataset/columns", mime_type="application/json")
def dataset_columns() -> dict:
    """Describe the fields on every request dict returned by the tools above.

    Read this before guessing a field name or grouping to filter or sort by.
    """
    return {
        "request_id": "The request's ID. Pass this to get_request.",
        "opened": "When the request was filed, in San Francisco local time, as an ISO 8601 string.",
        "closed": "When the request was closed, as an ISO 8601 string, or null while it is open.",
        "status": "'Open' or 'Closed'.",
        "service": "What the request is about, such as 'Graffiti Public'. Call dataset_info for the full list.",
        "subtype": "A finer category within service.",
        "agency": "The city team that owns the request.",
        "neighborhood": "One of the city's 41 official analysis neighborhoods, or '' when unknown.",
        "local_name": "The name people use for the area, such as 'Lower Nob Hill'. It can span several official neighborhoods.",
        "address": "Where the problem is, masked to the block, such as '900 block of HARRISON ST'. Intersections have no house number and are left as they are.",
        "source": "How it was filed: 'Mobile', 'Web', 'Phone', and others.",
    }


@mcp.tool(annotations=READ_ONLY)
def dataset_info() -> dict:
    """Describe the 311 dataset this server answers questions about.

    Call this first to learn the date range and the exact service and
    neighborhood names that other tools accept.
    """
    return {
        "description": "San Francisco 311 service requests filed in one week.",
        "first_opened": min(r.opened for r in REQUESTS).isoformat(),
        "last_opened": max(r.opened for r in REQUESTS).isoformat(),
        "requests": len(REQUESTS),
        "services": SERVICES,
        "neighborhoods": NEIGHBORHOODS,
        "local_neighborhood_names": len(LOCAL_NAMES),
    }


@mcp.tool(annotations=READ_ONLY)
def search_requests(
    service: str | None = None,
    neighborhood: str | None = None,
    status: Literal["Open", "Closed"] | None = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS)] = 20,
) -> list[dict]:
    """List individual 311 requests, newest first.

    Use this to show examples. For totals or rankings, use count_requests,
    which answers in one call without listing rows.
    """
    rows = sorted(_matching(service, neighborhood, status), key=lambda r: r.opened, reverse=True)
    return [_masked(r) for r in rows[:limit]]


@mcp.tool(annotations=READ_ONLY)
def count_requests(
    service: str | None = None,
    neighborhood: str | None = None,
    group_by: Literal["neighborhood", "service", "agency", "source", "weekday", "status"] | None = None,
) -> int | dict[str, int]:
    """Count 311 requests, optionally filtered by service and neighborhood.

    Without group_by, returns one number. With group_by, returns counts per
    group, largest first, so the first entry answers "which has the most".
    Use group_by="source" for how requests were filed, and group_by="weekday"
    for the day of the week.
    """
    rows = _matching(service, neighborhood)
    if group_by is None:
        return len(rows)
    key = GROUPS[group_by]
    return _ranked(Counter(key(r) for r in rows if key(r)))


@mcp.tool(annotations=READ_ONLY)
def median_close_hours(
    service: str | None = None,
    group_by: Literal["neighborhood", "agency"] | None = None,
) -> float | None | dict[str, float]:
    """Median hours from opened to closed, for closed requests only.

    With group_by, returns one median per group, fastest first. Groups with
    fewer than 10 closed requests are left out.
    """
    rows = [r for r in _matching(service, None) if r.hours_to_close is not None]
    if group_by is None:
        return round(median(r.hours_to_close for r in rows), 1) if rows else None
    key = GROUPS[group_by]
    hours = defaultdict(list)
    for r in rows:
        if key(r):
            hours[key(r)].append(r.hours_to_close)
    medians = {group: round(median(values), 1) for group, values in hours.items() if len(values) >= 10}
    return dict(sorted(medians.items(), key=lambda item: (item[1], item[0]))[:MAX_ROWS])


@mcp.tool(annotations=READ_ONLY)
def get_request(request_id: str) -> dict:
    """Return one 311 request by its ID."""
    request = BY_ID.get(request_id)
    if request is None:
        raise ToolError(f"No request with ID {request_id!r}. Use search_requests to find IDs.")
    logger.info("get_request %s requested by %s", request_id, caller_email() or "local")
    return _masked(request)


if __name__ == "__main__":
    mcp.run()
