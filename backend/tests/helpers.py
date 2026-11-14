def register(client, email="coach@example.com", org="Maple Grove Center", password="drumcircle1"):
    res = client.post(
        "/api/auth/register",
        json={
            "organization_name": org,
            "organization_type": "senior_center",
            "display_name": "Coach Lee",
            "email": email,
            "password": password,
        },
    )
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def auth_headers(client, **kw):
    token = register(client, **kw)["access_token"]
    return {"Authorization": f"Bearer {token}"}
