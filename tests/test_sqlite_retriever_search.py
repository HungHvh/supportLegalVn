import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from retrievers.sqlite_retriever import SQLiteFTS5Retriever

@pytest.mark.asyncio
async def test_aretrieve_articles_by_title_with_doc_type():
    retriever = SQLiteFTS5Retriever(db_path="dummy.db")
    retriever._article_fts_table = "article_titles_fts"
    
    mock_db = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = []
    mock_db.execute.return_value.__aenter__.return_value = mock_cursor
    
    with patch("aiosqlite.connect", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_db), __aexit__=AsyncMock())):
        # Test 1: doc_type = Luật
        await retriever.aretrieve_articles_by_title("test", doc_type="Luật")
        # Check what SQL was executed
        executed_sql, executed_params = mock_db.execute.call_args[0]
        assert "la.so_ky_hieu LIKE '%Luật%'" in executed_sql
        
        # Test 2: doc_type = Nghị định
        await retriever.aretrieve_articles_by_title("test", doc_type="Nghị định")
        executed_sql, executed_params = mock_db.execute.call_args[0]
        assert "la.so_ky_hieu LIKE '%NĐ-CP%'" in executed_sql
        
        # Test 3: doc_type = Thông tư
        await retriever.aretrieve_articles_by_title("test", doc_type="Thông tư")
        executed_sql, executed_params = mock_db.execute.call_args[0]
        assert "la.so_ky_hieu LIKE '%TT-%'" in executed_sql
        
        # Test 4: Custom doc_type
        await retriever.aretrieve_articles_by_title("test", doc_type="Quyết định")
        executed_sql, executed_params = mock_db.execute.call_args[0]
        assert "la.so_ky_hieu LIKE ?" in executed_sql
        assert "%Quyết định%" in executed_params
