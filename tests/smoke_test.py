"""Manual smoke test for the consolidated UAR UOR endpoints.

This file is intentionally not part of default CI validation. Run manually
when a UAR server (``uvicorn uar.api.server:app``) is reachable. The
endpoints exercised below are provided by ``uar/api/routers/uor.py``.
"""


def main():
    import requests

    base = "http://localhost:8000"

    obj1 = requests.post(f"{base}/objects", json={"content": 10}).json()[
        "digest"
    ]
    obj2 = requests.post(f"{base}/objects", json={"content": 20}).json()[
        "digest"
    ]

    workflow = {
        "name": "smoke",
        "inputs": [obj1, obj2],
        "steps": [
            {"runtimeName": "sum_contents"},
            {"runtimeName": "max_contents"},
        ],
    }

    res = requests.post(f"{base}/workflows/run", json=workflow).json()
    print("FINAL:", res)


if __name__ == "__main__":
    main()
