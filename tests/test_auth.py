from app import create_app


def test_login_page_loads():
    app = create_app()
    app.config.update(TESTING=True)

    client = app.test_client()
    response = client.get("/login")

    assert response.status_code == 200
    assert b"MemberMatch" in response.data
    assert b"Sign in" in response.data
