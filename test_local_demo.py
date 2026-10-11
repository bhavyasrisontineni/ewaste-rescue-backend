"""Small offline checks for the local web adapter's non-AI endpoints."""
import os
os.environ.setdefault("UPLOAD_BUCKET", "local-demo-bucket")
os.environ.setdefault("SCAN_TABLE", "LocalDemoScans")
os.environ.setdefault("CORS_ORIGIN", "http://127.0.0.1:5000")

from local_demo import app

def test_health():
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"

def test_unknown_guide_is_404():
    response = app.test_client().get("/api/disposal-guide/not_a_category")
    assert response.status_code == 404

if __name__ == "__main__":
    test_health()
    test_unknown_guide_is_404()
    print("Local adapter checks passed.")
