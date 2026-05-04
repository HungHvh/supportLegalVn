import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from retrievers.sqlite_retriever import SQLiteFTS5Retriever
from db.sqlite import normalize_so_ky_hieu

@pytest.mark.asyncio
async def test_aretrieve_articles_by_so_ky_hieu_with_doc_type():
    retriever = SQLiteFTS5Retriever(db_path="dummy.db")
    
    mock_db = MagicMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = []
    mock_execute_ctx = AsyncMock()
    mock_execute_ctx.__aenter__.return_value = mock_cursor
    mock_db.execute.return_value = mock_execute_ctx
    
    mock_connect = AsyncMock()
    mock_connect.__aenter__.return_value = mock_db
    mock_connect.__aexit__.return_value = False

    with patch("aiosqlite.connect", return_value=mock_connect):
        # Test 1: doc_type = Luật
        await retriever.aretrieve_articles_by_so_ky_hieu("test", doc_type="Luật")
        # Check what SQL was executed
        executed_sql, executed_params = mock_db.execute.call_args[0]
        assert "la.so_ky_hieu = ?" in executed_sql
        assert "lower(replace(replace(replace(la.so_ky_hieu" in executed_sql
        assert executed_params[0] == "test"
        assert executed_params[1] == normalize_so_ky_hieu("test")
        assert executed_params[2] == 50
        assert "la.article_path" not in executed_sql.split("WHERE")[1]
        
        # Test 2: doc_type = Nghị định
        await retriever.aretrieve_articles_by_so_ky_hieu("test", doc_type="Nghị định")
        executed_sql, executed_params = mock_db.execute.call_args[0]
        assert "la.so_ky_hieu LIKE '%NĐ-CP%'" in executed_sql
        
        # Test 3: doc_type = Thông tư
        await retriever.aretrieve_articles_by_so_ky_hieu("test", doc_type="Thông tư")
        executed_sql, executed_params = mock_db.execute.call_args[0]
        assert "la.so_ky_hieu LIKE '%TT-%'" in executed_sql
        
        # Test 4: Custom doc_type
        await retriever.aretrieve_articles_by_so_ky_hieu("test", doc_type="Quyết định")
        executed_sql, executed_params = mock_db.execute.call_args[0]
        assert "la.so_ky_hieu LIKE ?" in executed_sql
        assert "%Quyết định%" in executed_params


@pytest.mark.asyncio
async def test_aretrieve_articles_by_so_ky_hieu_keeps_raw_identifier():
    retriever = SQLiteFTS5Retriever(db_path="dummy.db")

    mock_db = MagicMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = []
    mock_execute_ctx = AsyncMock()
    mock_execute_ctx.__aenter__.return_value = mock_cursor
    mock_db.execute.return_value = mock_execute_ctx

    mock_connect = AsyncMock()
    mock_connect.__aenter__.return_value = mock_db
    mock_connect.__aexit__.return_value = False

    raw_identifier = "123/2024/NĐ-CP"
    with patch("aiosqlite.connect", return_value=mock_connect):
        await retriever.aretrieve_articles_by_so_ky_hieu(raw_identifier)

        executed_sql, executed_params = mock_db.execute.call_args[0]
        assert executed_params[0] == raw_identifier
        assert executed_params[1] == normalize_so_ky_hieu(raw_identifier)
        assert executed_params[2] == 50


