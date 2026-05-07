import { useState, useCallback, useEffect } from 'react';
import { buildApiUrl } from '@/lib/apiBaseUrl';

export interface ArticleResult {
  article_uuid: string;
  doc_id?: string;
  so_ky_hieu?: string;
  title?: string;
  score: number;
  full_content: string;
  doc_type?: string;
  highlighted_content?: string;
}

export interface SearchArticlesResponse {
  query: string;
  top_results_count: number;
  results: ArticleResult[];
  status: string;
}

export function useSearchHighlight() {
  const [activeHighlightIndex, setActiveHighlightIndex] = useState(0);
  const [highlightCount, setHighlightCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [articleData, setArticleData] = useState<ArticleResult | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const nextHighlight = useCallback(() => {
    setActiveHighlightIndex((prev) => (prev < highlightCount - 1 ? prev + 1 : prev));
  }, [highlightCount]);

  const prevHighlight = useCallback(() => {
    setActiveHighlightIndex((prev) => (prev > 0 ? prev - 1 : prev));
  }, []);

  const fetchArticle = useCallback(async (query: string, searchPhrase?: string, article_uuid?: string) => {
    setLoading(true);
    setError(null);
    setSearchQuery(searchPhrase || "");
    try {
      // Using query to search by so_ky_hieu and searchPhrase to highlight text
      const requestBody: any = { query: query };
      if (article_uuid) {
        requestBody.article_uuid = article_uuid;
      }
      
      const response = await fetch(buildApiUrl("/api/v1/search-articles"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch article");
      }

      const data: SearchArticlesResponse = await response.json();
      if (data.results && data.results.length > 0) {
        // Find best match, default to first
        let bestResult = data.results[0];
        
        // If we have a specific phrase to highlight, we could potentially re-highlight here
        // or just use the backend's highlighted_content
        
        setArticleData(bestResult);
        setActiveHighlightIndex(0);
      } else {
        setError("Không tìm thấy dữ liệu bài viết.");
        setArticleData(null);
        setHighlightCount(0);
      }
    } catch (err) {
      console.error(err);
      setError("Có lỗi xảy ra khi tải bài viết.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Compute highlight count when articleData or searchQuery changes
  useEffect(() => {
    if (articleData) {
      if (articleData.highlighted_content) {
        const count = (articleData.highlighted_content.match(/<b>/g) || []).length;
        setHighlightCount(count);
      } else {
        setHighlightCount(0);
      }
    }
  }, [articleData, searchQuery]);

  return {
    activeHighlightIndex,
    highlightCount,
    loading,
    error,
    articleData,
    nextHighlight,
    prevHighlight,
    fetchArticle
  };
}
