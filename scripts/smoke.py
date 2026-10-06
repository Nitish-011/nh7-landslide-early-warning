#!/usr/bin/env python3
"""
Cross-platform smoke test runner for NH-7 Landslide Risk API.
Tests live endpoints against a running server at BASE_URL.
Zero shell dependencies.
"""
import os
import sys
import time
import json
import urllib.request
import urllib.error

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")

def run_request(method, path, body=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"} if body else {}
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            latency_ms = (time.perf_counter() - t0) * 1000
            content = response.read()
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "latency_ms": latency_ms,
                "data": json.loads(content) if "application/json" in response.headers.get("Content-Type", "") else None
            }
    except urllib.error.HTTPError as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return {
            "ok": False,
            "status": e.code,
            "latency_ms": latency_ms,
            "error": str(e)
        }
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return {
            "ok": False,
            "status": 0,
            "latency_ms": latency_ms,
            "error": str(e)
        }


def main():
    print(f"=== NH-7 API Smoke Test Runner ===")
    print(f"Target Server: {BASE_URL}\n")

    endpoints = [
        ("GET", "/health", None),
        ("GET", "/", None),
        ("GET", "/risk-map", None),
        ("GET", "/risk-map?simulate_rain_mm=50", None),
        ("GET", "/route-risk?from_segment=seg_01&to_segment=seg_05&date=2026-10-06", None),
        ("POST", "/subscribe", {
            "name": "Smoke Test Driver",
            "phone_or_email": "+91-9876500000",
            "segment_id": "seg_01",
            "channel": "SMS"
        }),
        ("GET", "/alerts?user_id=1", None),
        ("POST", "/field-report", {
            "lat": round(30.14 + ((int(time.time()) % 10) * 0.001), 4),
            "lng": round(78.36 + ((int(time.time()) % 10) * 0.001), 4),
            "description": f"Smoke test observation near Shivpuri - {int(time.time())}",
            "reporter_name": "Automated Smoke Test"
        }),
        ("GET", "/field-reports", None),
        ("GET", "/history", None),
        ("GET", "/model-info", None),
        ("GET", "/priority-list", None),
        ("GET", "/priority-list?simulate_rain_mm=40", None),
        ("GET", "/closures", None),
        ("GET", "/risk-map?lang=hi", None),
        ("GET", "/route-risk?from_segment=seg_01&to_segment=seg_05&date=2026-10-06&lang=hi", None),
        ("GET", "/alerts?user_id=1&lang=hi", None),
        ("GET", "/voice-alert?segment_id=seg_01&lang=hi", None),
    ]

    all_passed = True
    created_report_id = None

    for method, path, body in endpoints:
        res = run_request(method, path, body)
        latency = f"{res['latency_ms']:.1f}ms"

        if res["ok"]:
            print(f"[PASS] {method:4s} {path:<60} {latency:>8} (HTTP {res['status']})")
            if path == "/field-report" and res["data"] and "report_id" in res["data"]:
                created_report_id = res["data"]["report_id"]
        else:
            all_passed = False
            err_info = res.get("error") or f"HTTP {res['status']}"
            print(f"[FAIL] {method:4s} {path:<60} {latency:>8} ({err_info})")

    # If report was created, test admin validation
    if created_report_id:
        val_path = "/admin/validate-report"
        val_body = {
            "report_id": created_report_id,
            "decision": "Validated",
            "notes": "Validated via automated smoke test"
        }
        res = run_request("POST", val_path, val_body)
        latency = f"{res['latency_ms']:.1f}ms"
        if res["ok"]:
            print(f"[PASS] POST {val_path:<60} {latency:>8} (HTTP {res['status']})")
        else:
            all_passed = False
            print(f"[FAIL] POST {val_path:<60} {latency:>8} (HTTP {res['status']})")

    print("\n" + ("=" * 40))
    if all_passed:
        print("ALL SMOKE TESTS PASSED!")
        sys.exit(0)
    else:
        print("SMOKE TESTS FAILED - Check server logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
