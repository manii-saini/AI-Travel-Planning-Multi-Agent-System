from tools.qrail_tool import search_flights, search_trains


def test_search_flights_handles_missing_qrail_key():
    result = search_flights("Delhi to Mumbai")
    assert isinstance(result, str)
    assert len(result) > 40
    assert "Airline:" in result or "Flight No:" in result or "No live flight" in result


def test_search_trains_handles_missing_qrail_key():
    result = search_trains("Delhi to Jaipur")
    assert isinstance(result, str)
    assert len(result) > 40
    assert "Train" in result or "Jaipur" in result or "https://" in result or "No train" in result
