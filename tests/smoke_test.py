import requests

BASE = "http://localhost:8000"

# create objects
obj1 = requests.post(f"{BASE}/objects", json={"content": 10}).json()["digest"]
obj2 = requests.post(f"{BASE}/objects", json={"content": 20}).json()["digest"]

# run workflow
workflow = {
    "name": "smoke",
    "inputs": [obj1, obj2],
    "steps": [
        {"runtimeName": "sum_contents"},
        {"runtimeName": "max_contents"}
    ]
}

res = requests.post(f"{BASE}/workflows/run", json=workflow).json()

print("FINAL:", res)
