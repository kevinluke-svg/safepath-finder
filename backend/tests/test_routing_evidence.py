from fastapi.testclient import TestClient


def test_route_compare_response_schema(client: TestClient):
    """
    POST /api/v1/routes/compare returns route id, geometry, distanceMeters,
    durationSeconds, characteristics, evidenceSummary, and explanation.
    """
    payload = {
        "origin": "Jayanagar 4th Block, Bengaluru",
        "destination": "Lalbagh West Gate, Bengaluru",
        "walkingMode": "pedestrian",
        "preferences": {
            "preferLighting": True,
            "avoidUnknown": True
        }
    }
    response = client.post("/api/v1/routes/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["origin"] == payload["origin"]
    assert data["destination"] == payload["destination"]
    assert len(data["routes"]) == 3

    for r in data["routes"]:
        assert "id" in r
        assert "geometry" in r
        assert len(r["geometry"]) >= 2
        assert isinstance(r["distanceMeters"], int)
        assert isinstance(r["durationSeconds"], int)
        assert isinstance(r["characteristics"], list)
        assert "evidenceSummary" in r
        assert "coverage" in r["evidenceSummary"]
        assert "freshnessState" in r["evidenceSummary"]
        assert "riskEstimate" in r["evidenceSummary"]
        assert isinstance(r["explanation"], str)
        assert isinstance(r["tradeoffs"], str)


def test_preference_weights_affect_ranking(client: TestClient):
    """Multi-attribute utility weights adjust route ranking order."""
    # 1. Lighting and evidence prioritized
    res1 = client.post("/api/v1/routes/compare", json={
        "origin": "Jayanagar",
        "destination": "Lalbagh",
        "preferences": {"preferLighting": True, "avoidUnknown": True}
    })
    routes1 = res1.json()["routes"]
    assert routes1[0]["id"] == "route-evidence"
    assert "Evidence-led Route ranks #1" in res1.json()["rankingReason"]

    # 2. Time prioritized over evidence
    res2 = client.post("/api/v1/routes/compare", json={
        "origin": "Jayanagar",
        "destination": "Lalbagh",
        "preferences": {"preferLighting": False, "avoidUnknown": False}
    })
    routes2 = res2.json()["routes"]
    assert routes2[0]["id"] == "route-shortest"
    assert "Shortest Sample Route ranks #1" in res2.json()["rankingReason"]


def test_evidence_segments_inspection(client: TestClient):
    """
    GET /api/v1/evidence/segments?routeId=... returns source, observedAt, coverage,
    freshness, state (available, limited, or insufficient), optional riskEstimate, and limitations.
    """
    response = client.get("/api/v1/evidence/segments?routeId=route-evidence")
    assert response.status_code == 200
    data = response.json()
    assert data["routeId"] == "route-evidence"
    assert len(data["segments"]) >= 3

    for seg in data["segments"]:
        assert "id" in seg
        assert "streetName" in seg
        assert "source" in seg
        assert "observedAt" in seg
        assert seg["coverage"] in ["adequate", "limited", "insufficient"]
        assert seg["freshness"] in ["fresh", "stale", "outdated"]
        assert seg["state"] in ["available", "limited", "insufficient"]
        assert isinstance(seg["limitations"], list)
        assert isinstance(seg["timeline"], list)


def test_missing_data_never_encoded_as_low_risk(client: TestClient):
    """
    Core research principle: missing or undocumented observations must never be encoded as low risk.
    """
    response = client.get("/api/v1/evidence/segments?routeId=route-evidence")
    data = response.json()
    stale_or_limited = [s for s in data["segments"] if s["coverage"] != "adequate"]
    assert len(stale_or_limited) > 0
    for s in stale_or_limited:
        assert "low risk" not in (s.get("riskEstimate") or "").lower()
