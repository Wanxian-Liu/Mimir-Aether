from tools.code_execution_tool import build_execute_code_schema


def test_execute_code_schema_mentions_only_enabled_tools():
    schema = build_execute_code_schema(enabled_sandbox_tools={"terminal"})
    desc = schema["description"]

    assert "terminal(command:" in desc
    assert "web_search(query:" not in desc
    assert "web_extract(urls:" not in desc
    assert "read_file(path:" not in desc


def test_execute_code_schema_contains_import_examples():
    schema = build_execute_code_schema(enabled_sandbox_tools={"terminal"})
    code_desc = schema["parameters"]["properties"]["code"]["description"]
    assert "from hermes_tools import" in code_desc
    assert "terminal" in code_desc

