import os
from typing import Any

import requests
from dotenv import load_dotenv

from tools.tavily_tool import tavily_search

load_dotenv()

QRAIL_API_KEY = os.getenv("QRAIL_API_KEY")
QRAIL_BASE_URLS = [
    "https://api.qrail.io",
    "https://api.qrail.app",
    "https://api.qrail.com",
    "https://api.qrail.ai",
    "https://qrail.io/api",
]
AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY") or os.getenv("AVIATION_API_KEY")


def _normalize_items(payload: Any):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    for key in ("data", "results", "items", "flights", "trains", "journeys"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _normalize_items(value)
            if nested:
                return nested

    result = payload.get("result")
    if isinstance(result, dict):
        return _normalize_items(result)
    return []


def _format_flight(item: Any) -> str:
    if not isinstance(item, dict):
        return str(item)

    airline = item.get("airline") or item.get("carrier") or item.get("airline_name") or "Unknown"
    if isinstance(airline, dict):
        airline = airline.get("name") or airline.get("carrier_name") or "Unknown"

    flight_no = (
        item.get("flight_number")
        or item.get("flightNo")
        or item.get("number")
        or ((item.get("flight") or {}).get("number"))
        or "N/A"
    )
    departure = (
        item.get("departure")
        or item.get("from")
        or item.get("origin")
        or ((item.get("departure_airport") or {}).get("name") if isinstance(item.get("departure_airport"), dict) else item.get("departure_airport"))
        or "Unknown"
    )
    arrival = (
        item.get("arrival")
        or item.get("to")
        or item.get("destination")
        or ((item.get("arrival_airport") or {}).get("name") if isinstance(item.get("arrival_airport"), dict) else item.get("arrival_airport"))
        or "Unknown"
    )
    status = item.get("status") or item.get("flight_status") or "scheduled"
    price = item.get("price") or item.get("fare") or item.get("amount") or "N/A"

    return (
        f"Airline: {airline}\n"
        f"Flight No: {flight_no}\n"
        f"Departure: {departure}\n"
        f"Arrival: {arrival}\n"
        f"Status: {status}\n"
        f"Price: {price}\n---"
    )


def _format_train(item: Any) -> str:
    if not isinstance(item, dict):
        return str(item)

    train_name = item.get("train_name") or item.get("name") or item.get("train") or "Unknown"
    train_no = item.get("train_number") or item.get("trainNo") or item.get("number") or "N/A"
    from_station = (
        item.get("from_station")
        or item.get("source")
        or item.get("origin")
        or item.get("departure_station")
        or "Unknown"
    )
    to_station = (
        item.get("to_station")
        or item.get("destination")
        or item.get("arrival_station")
        or item.get("destination_station")
        or "Unknown"
    )
    departure_time = item.get("departure_time") or item.get("departure") or item.get("start_time") or "N/A"
    arrival_time = item.get("arrival_time") or item.get("arrival") or item.get("end_time") or "N/A"
    price = item.get("price") or item.get("fare") or item.get("amount") or "N/A"

    return (
        f"Train: {train_name}\n"
        f"Train No: {train_no}\n"
        f"From: {from_station}\n"
        f"To: {to_station}\n"
        f"Departure: {departure_time}\n"
        f"Arrival: {arrival_time}\n"
        f"Price: {price}\n---"
    )


def _request_transport(kind: str, query: str, *, route: str = "search") -> str:
    if not QRAIL_API_KEY:
        return f"{kind.title()} API key is missing. Please set QRAIL_API_KEY in your .env file."

    endpoints = []
    for base in QRAIL_BASE_URLS:
        endpoints.extend(
            [
                f"{base.rstrip('/')}/{route}",
                f"{base.rstrip('/')}/{kind}",
                f"{base.rstrip('/')}/{kind}/{route}",
                f"{base.rstrip('/')}/v1/{route}",
                f"{base.rstrip('/')}/v1/{kind}",
                f"{base.rstrip('/')}/v1/{kind}/{route}",
            ]
        )

    headers = {
        "Authorization": f"Bearer {QRAIL_API_KEY}",
        "X-API-Key": QRAIL_API_KEY,
        "Accept": "application/json",
    }

    for url in endpoints:
        try:
            response = requests.get(
                url,
                params={
                    "q": query,
                    "query": query,
                    "api_key": QRAIL_API_KEY,
                    "type": kind,
                    "route": route,
                },
                headers=headers,
                timeout=20,
            )
        except requests.RequestException:
            continue

        if response.status_code in (401, 403):
            return f"QRAIL {kind} API authentication failed. Check the QRAIL_API_KEY value in your .env file."
        if response.status_code in (404, 405):
            continue
        if response.status_code >= 400:
            continue

        try:
            payload = response.json()
        except ValueError:
            continue

        items = _normalize_items(payload)
        if not items:
            if isinstance(payload, dict) and payload.get("message"):
                return str(payload["message"])
            continue

        formatted = []
        for item in items[:5]:
            formatted.append(_format_flight(item) if kind == "flight" else _format_train(item))

        if formatted:
            return "\n".join(formatted)

    return f"No {kind} data returned from the QRAIL API for '{query}'. Please check the API endpoint or try a different route."


def _fallback_flights(query: str) -> str:
    if not AVIATIONSTACK_API_KEY:
        return "Flight API key is missing. Please set AVIATIONSTACK_API_KEY or AVIATION_API_KEY in your .env file."

    url = "http://api.aviationstack.com/v1/flights"
    params = {
        "access_key": AVIATIONSTACK_API_KEY,
        "limit": 5,
        "flight_status": "scheduled",
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Flight API request failed: {exc}"

    try:
        data = response.json()
    except ValueError:
        return "Flight API returned invalid JSON."

    flights = []
    for flight in data.get("data", [])[:5]:
        airline = flight.get("airline", {}).get("name", "Unknown")
        departure = flight.get("departure", {}).get("airport", "Unknown")
        arrival = flight.get("arrival", {}).get("airport", "Unknown")
        status = flight.get("flight_status", "Unknown")
        flight_no = flight.get("flight", {}).get("number", "N/A")
        flights.append(
            f"""Airline: {airline}
Flight No: {flight_no}
Departure: {departure}
Arrival: {arrival}
Status: {status}
---"""
        )

    if not flights:
        return "No live flight data available right now. Please try again later."

    return "\n".join(flights)


def _fallback_trains(query: str) -> str:
    try:
        results = tavily_search(f"Train timetable, fare, and route options for {query}")
    except Exception as exc:
        return f"Train search failed: {exc}"

    if not results:
        return "No train options found for this route right now."

    lines = []
    for item in results.split("\n\n")[:5]:
        title = ""
        link = ""
        detail = ""

        for line in item.splitlines():
            trimmed = line.strip()
            if not trimmed:
                continue
            if trimmed.startswith("http"):
                link = trimmed
            elif trimmed.startswith(("1.", "2.", "3.", "4.", "5.")):
                title = trimmed.split("**", 1)[1].split("**", 1)[0] if "**" in trimmed else trimmed
            elif not detail:
                detail = trimmed

        if not title:
            title = query
        if not detail:
            detail = "Route details available from the source link."

        lines.append(
            f"Train Route: {query}\n"
            f"Train Service: {title}\n"
            f"Link: {link or 'N/A'}\n"
            f"Details: {detail[:220]}\n---"
        )

    return "\n".join(lines)


def search_flights(query: str) -> str:
    """Fetch flights using QRAIL if available, else fall back to AviationStack."""
    qrail_result = _request_transport("flight", query, route="search")
    if "No flight data returned" not in qrail_result and "QRAIL" not in qrail_result and "missing" not in qrail_result.lower():
        return qrail_result
    return _fallback_flights(query)


def search_trains(query: str) -> str:
    """Fetch train options using QRAIL if available, else use web search fallback."""
    qrail_result = _request_transport("train", query, route="search")
    if "No train data returned" not in qrail_result and "QRAIL" not in qrail_result and "missing" not in qrail_result.lower():
        return qrail_result
    return _fallback_trains(query)
