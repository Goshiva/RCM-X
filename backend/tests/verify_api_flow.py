from flask import Flask

from backend.app.api.auth.auth_routes import bp as auth_bp
from backend.app.api.dashboard.dashboard_routes import bp as dashboard_bp
from backend.app.services.auth_service import default_auth_service

app = Flask(__name__)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)

def main() -> None:
    default_auth_service.register_user("coder1", "coder1@example.com", "Secret123!", "coder")
    client = app.test_client()
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "coder1", "password": "Secret123!"},
    )
    print(login_resp.status_code)
    print(login_resp.get_json()["success"])
    token = login_resp.get_json()["access_token"]
    auth_resp = client.get(
        "/api/dashboard/coder",
        headers={"Authorization": f"Bearer {token}"},
    )
    print(auth_resp.status_code)
    print(auth_resp.get_json()["success"])


if __name__ == "__main__":
    main()
