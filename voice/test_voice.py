"""
Basic smoke-test for the voice agent webhook endpoint.
Simulates Vapi function-call events and prints results.

Usage:
    cd voice
    python test_voice.py --url http://localhost:8000
"""

import argparse

import httpx


def make_function_call_payload(function_name: str, parameters: dict) -> dict:
    return {
        "message": {
            "type": "function-call",
            "functionCall": {
                "name": function_name,
                "parameters": parameters,
            },
        }
    }


def test_endpoint(base_url: str):
    webhook_url = f"{base_url}/api/voice/vapi/webhook"
    results = []

    test_cases = [
        {
            "label": "get_background_info",
            "payload": make_function_call_payload(
                "get_background_info",
                {"question": "What is your experience with RAG systems?"},
            ),
        },
        {
            "label": "get_availability",
            "payload": make_function_call_payload("get_availability", {}),
        },
        {
            "label": "get_github_info",
            "payload": make_function_call_payload(
                "get_github_info",
                {
                    "repo_name": "ai-persona",
                    "question": "What tech stack does this project use?",
                },
            ),
        },
        {
            "label": "book_meeting (incomplete — missing email)",
            "payload": make_function_call_payload(
                "book_meeting",
                {"name": "Jane Smith", "datetime": "2024-03-20T14:00:00Z"},
            ),
        },
    ]

    with httpx.Client(timeout=30) as client:
        for case in test_cases:
            print(f"\n{'='*60}")
            print(f"TEST: {case['label']}")
            print(f"{'='*60}")
            try:
                res = client.post(webhook_url, json=case["payload"])
                res.raise_for_status()
                data = res.json()
                result_text = data.get("result", str(data))
                print(f"RESPONSE ({len(str(result_text))} chars):")
                print(str(result_text)[:500])
                results.append({"label": case["label"], "status": "PASS"})
            except Exception as e:
                print(f"ERROR: {e}")
                results.append({"label": case["label"], "status": "FAIL", "error": str(e)})

    print("\n\n📊 RESULTS SUMMARY")
    print("=" * 40)
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"{icon} {r['label']}: {r['status']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    test_endpoint(args.url)
