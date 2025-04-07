import pytest
from app import app
from dotenv import load_dotenv
load_dotenv()

@pytest.fixture()
def client():
    app.testing = True
    return app.test_client()

@pytest.fixture()
def admin_client(client):
    resp = client.post("/login", data={"username": "admin", "password": "password"})
    assert(resp.status_code == 200)
    print(client.get("/", follow_redirects=True).data)
    return client

def test_index(admin_client):
    resp = admin_client.get("/")
    assert(resp.status_code == 200)