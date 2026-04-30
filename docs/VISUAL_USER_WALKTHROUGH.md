# Visual User Walkthrough

This is the dummy-proof path. Do not improvise. Follow the boxes in order.

## 0. Goal

By the end, you will prove UAR can:

```text
create object → run runtime → run workflow → trace output
```

## 1. Start the server

```bash
cd apps/api-python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
fastapi dev main.py
```

Expected screen clue:

```text
Uvicorn running on http://127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8000/docs
```

You should see the FastAPI Swagger page.

---

## 2. Create two objects

In `/docs`, open:

```text
POST /objects
```

Click **Try it out**.

Paste this:

```json
{
  "content": 10,
  "attributes": {"kind": "demo-number"}
}
```

Click **Execute**.

Copy the returned `digest`.

Repeat with:

```json
{
  "content": 20,
  "attributes": {"kind": "demo-number"}
}
```

You now have two object digests.

---

## 3. List runtimes

Open:

```text
GET /runtimes
```

Click **Try it out → Execute**.

You should see:

```text
sum_contents
identity_value
count_inputs
```

---

## 4. Execute a runtime

Open:

```text
POST /agents/execution/run
```

Paste this, replacing the digest strings:

```json
{
  "runtimeName": "sum_contents",
  "inputs": [
    "sha256:PASTE_FIRST_DIGEST",
    "sha256:PASTE_SECOND_DIGEST"
  ]
}
```

Expected result:

```json
"result": 30
```

Copy the `output` digest.

---

## 5. Run a workflow

Open:

```text
POST /workflows/run
```

Paste this:

```json
{
  "name": "demo-workflow",
  "inputs": [
    "sha256:PASTE_FIRST_DIGEST",
    "sha256:PASTE_SECOND_DIGEST"
  ],
  "steps": [
    {"runtimeName": "sum_contents"},
    {"runtimeName": "identity_value"}
  ]
}
```

Expected result:

```text
step 1 result = 30
step 2 result = 30
```

Copy the `finalOutput` digest.

---

## 6. Trace lineage

Open:

```text
GET /agents/lineage/trace
```

Paste the final output digest into the `digest` field.

Expected clue:

```text
created
executed
```

---

## 7. You are done when

You can say:

```text
I created two objects, ran a runtime, ran a workflow, and traced the result.
```

## If something fails

Do not guess. Capture:

- endpoint name
- request body
- response body
- screenshot if possible

Then file it under Issue #3: Truth Validation Run.
