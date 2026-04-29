# (same as before but modify execution section)
# shortened for patch clarity

# REPLACE ONLY execution_run function

@app.post("/agents/execution/run")
def execution_run(req: ExecuteReq):
    for digest in req.inputs:
        get_obj(digest)

    result = None
    if "code" in req.parameters:
        try:
            # very basic safe eval sandbox
            allowed_builtins = {"len": len, "sum": sum}
            result = eval(req.parameters["code"], {"__builtins__": allowed_builtins}, {})
        except Exception as e:
            result = str(e)

    output = create_record(
        mediaType="application/vnd.uar.execution-output+json",
        mode="immutable",
        attributes={"agent": "execution"},
        links=[{"rel": "used", "target": d} for d in req.inputs],
        content={"result": result},
    )

    return {"output": output["digest"], "result": result}
