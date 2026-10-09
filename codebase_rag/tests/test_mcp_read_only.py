import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from codebase_rag import constants as cs
from codebase_rag.mcp import server as srv
from codebase_rag.mcp.tools import MCPToolsRegistry
from codebase_rag.workspaces import WorkspaceConfig, WorkspaceRepo


@pytest.mark.anyio
async def test_read_only_filters_and_refuses_dispatch(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CGR_MCP_READ_ONLY", "1")
    monkeypatch.setenv("TARGET_REPO_PATH", str(tmp_path))
    (tmp_path / "README.md").write_text("readable\n")
    with (
        patch.object(srv, "MemgraphIngestor", return_value=MagicMock()),
        patch.object(srv, "LazyCypherGenerator", MagicMock()),
    ):
        server, _ = srv.create_server()
    async with create_connected_server_and_client_session(server) as client:
        listed = await client.list_tools()
        assert {tool.name for tool in listed.tools} == {
            "list_projects",
            "resolve",
            "definition",
            "callers",
            "callees",
            "implementors",
            "overrides",
            "importers",
            "tests_reaching",
            "read_file",
            "list_directory",
        }
        with patch.object(MCPToolsRegistry, "get_tool_handler") as lookup:
            for name in (set(cs.MCPToolName) - srv.READ_ONLY_TOOLS) | {"future_tool"}:
                result = await client.call_tool(name, {})
                assert result.isError
                assert "disabled in read-only mode" in result.content[0].text
            lookup.assert_not_called()
        result = await client.call_tool("read_file", {"file_path": "README.md"})
        assert not result.isError
        assert "readable" in result.content[0].text
        escaped = await client.call_tool("read_file", {"file_path": "../outside"})
        assert escaped.isError
    assert (tmp_path / "README.md").read_text() == "readable\n"


@pytest.mark.anyio
async def test_default_mode_preserves_writes(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("CGR_MCP_READ_ONLY", raising=False)
    monkeypatch.setenv("TARGET_REPO_PATH", str(tmp_path))
    with (
        patch.object(srv, "MemgraphIngestor", return_value=MagicMock()),
        patch.object(srv, "LazyCypherGenerator", MagicMock()),
    ):
        server, _ = srv.create_server()
    async with create_connected_server_and_client_session(server) as client:
        listed = await client.list_tools()
        assert "write_file" in {tool.name for tool in listed.tools}
        result = await client.call_tool(
            "write_file", {"file_path": "new.md", "content": "ok"}
        )
        assert not result.isError
    assert (tmp_path / "new.md").read_text() == "ok"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_read_only_refuses_stranded_marker_without_writes():
    registry = MCPToolsRegistry.__new__(MCPToolsRegistry)
    registry.read_only = True
    registry.ingestor = MagicMock()
    registry.ingestor.fetch_all.return_value = [
        {"run_incomplete": True, "writing": False}
    ]
    assert registry._persisted_incomplete("backend") is True
    registry.ingestor.execute_write.assert_not_called()


@pytest.mark.anyio
async def test_workspace_reads_are_scoped_per_request(tmp_path: Path, monkeypatch):
    roots = {name: tmp_path / name for name in ["backend", "admin"]}
    for name, root in roots.items():
        root.mkdir()
        (root / "README.md").write_text(name + "\nsecond\n")
    (roots["admin"] / "escape").symlink_to(roots["backend"] / "README.md")
    monkeypatch.setenv("CGR_MCP_READ_ONLY", "1")
    monkeypatch.setenv("TARGET_REPO_PATH", str(roots["backend"]))
    workspace = WorkspaceConfig(
        name="test",
        repos=[
            WorkspaceRepo(path=str(root), project_name=name)
            for name, root in roots.items()
        ],
    )
    ingestor = MagicMock()
    ingestor.fetch_all.side_effect = lambda query, params: [
        {"root_path": str(roots[params["project_name"]])}
    ]
    with (
        patch.object(srv, "MemgraphIngestor", return_value=ingestor),
        patch.object(srv, "LazyCypherGenerator", MagicMock()),
        patch.object(srv, "get_workspace", return_value=workspace),
    ):
        server, _ = srv.create_server()
    async with create_connected_server_and_client_session(server) as client:
        results = await asyncio.gather(
            *[
                client.call_tool(
                    "read_file", {"file_path": "README.md", "project": name}
                )
                for name in roots
            ]
        )
        for name, result in zip(roots, results):
            assert not result.isError
            assert result.content[0].text.startswith(name + "\n")
        paged = await client.call_tool(
            "read_file",
            {
                "file_path": "README.md",
                "project": "admin",
                "offset": 0,
                "limit": 1,
            },
        )
        assert not paged.isError and "admin\n" in paged.content[0].text
        for file_path in ["escape", "../backend/README.md"]:
            for extra in [{}, {"offset": 0, "limit": 1}]:
                result = await client.call_tool(
                    "read_file",
                    {
                        "file_path": file_path,
                        "project": "admin",
                        **extra,
                    },
                )
                assert result.isError
        unknown = await client.call_tool(
            "read_file", {"file_path": "README.md", "project": "other"}
        )
        assert unknown.isError
        ingestor.fetch_all.side_effect = None
        ingestor.fetch_all.return_value = [{"root_path": str(tmp_path / "wrong")}]
        unproven = await client.call_tool(
            "read_file", {"file_path": "README.md", "project": "admin"}
        )
        assert unproven.isError
