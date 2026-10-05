import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
import app.risk_service as RS

GOLDEN_DIR = Path("tests/golden")
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

client = TestClient(app)

MOCK_RAIN = {
    f"seg_{i:02d}": {"rain_mm": 18.5, "status": "ok"}
    for i in range(1, 19)
}

def generate_golden():
    with patch("app.risk_service.fetch_rainfall", return_value=MOCK_RAIN):
        # 1. Health
        r = client.get("/health")
        assert r.status_code == 200
        (GOLDEN_DIR / "health_golden.json").write_text(json.dumps(r.json(), indent=2), encoding="utf-8")

        # 2. Risk Map
        r = client.get("/risk-map")
        assert r.status_code == 200
        (GOLDEN_DIR / "risk_map_golden.json").write_text(json.dumps(r.json(), indent=2), encoding="utf-8")

        # 3. Route Risk
        r = client.get("/route-risk?from_segment=seg_01&to_segment=seg_04&date=2026-10-06")
        assert r.status_code == 200
        (GOLDEN_DIR / "route_risk_golden.json").write_text(json.dumps(r.json(), indent=2), encoding="utf-8")

        # 4. Subscribe
        sub_payload = {
            "name": "Ramesh Kumar",
            "phone_or_email": "+91-9876543210",
            "segment_id": "seg_01",
            "channel": "SMS"
        }
        r = client.post("/subscribe", json=sub_payload)
        assert r.status_code in (200, 201)
        sub_data = r.json()
        sub_id = sub_data["subscription_id"]
        (GOLDEN_DIR / "subscribe_golden.json").write_text(json.dumps(sub_data, indent=2), encoding="utf-8")

        # 5. Alerts
        r = client.get(f"/alerts?user_id={sub_id}")
        assert r.status_code == 200
        (GOLDEN_DIR / "alerts_golden.json").write_text(json.dumps(r.json(), indent=2), encoding="utf-8")

        # 6. Field Report Submit
        rep_payload = {
            "lat": 30.12,
            "lng": 78.32,
            "description": "Small rockfall near Byasi bend",
            "reporter_name": "Patrol Team 1"
        }
        r = client.post("/field-report", json=rep_payload)
        assert r.status_code in (200, 201)
        rep_data = r.json()
        rep_id = rep_data["report_id"]
        (GOLDEN_DIR / "field_report_golden.json").write_text(json.dumps(rep_data, indent=2), encoding="utf-8")

        # 7. Admin Validate
        val_payload = {
            "report_id": rep_id,
            "decision": "Validated",
            "notes": "Verified by ground team"
        }
        r = client.post("/admin/validate-report", json=val_payload)
        assert r.status_code == 200
        (GOLDEN_DIR / "admin_validate_golden.json").write_text(json.dumps(r.json(), indent=2), encoding="utf-8")

        # 8. Field Reports List
        r = client.get("/field-reports")
        assert r.status_code == 200
        (GOLDEN_DIR / "field_reports_list_golden.json").write_text(json.dumps(r.json(), indent=2), encoding="utf-8")

        # 9. History
        r = client.get("/history")
        assert r.status_code == 200
        (GOLDEN_DIR / "history_golden.json").write_text(json.dumps(r.json(), indent=2), encoding="utf-8")

    print(f"Golden files generated successfully in {GOLDEN_DIR.resolve()}")

if __name__ == "__main__":
    generate_golden()
