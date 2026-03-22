from agents.bq_tools import execute_tool


def test_execute_tool_rejects_unknown() -> None:
    r = execute_tool("arbitrary_sql", {"q": "DROP TABLE users"})
    assert "error" in r
    assert "Unknown tool" in r["error"]


def test_tool_registry_keys() -> None:
    from agents.bq_tools import TOOL_REGISTRY

    assert "source_row_counts" in TOOL_REGISTRY
    assert "raw_table_health" in TOOL_REGISTRY
