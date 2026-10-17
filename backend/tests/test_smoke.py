def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_logistic_smoke(client, auth_headers, ml_request):
    response = client.post(
        "/api/ml/logistic",
        json=ml_request(variable_types={"结局Y1": "logical"}),
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
