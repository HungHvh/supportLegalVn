import { useState, useEffect, useRef } from "react";
import { Citation } from "@/app/page";
import { BookOpen, ChevronLeft, ChevronRight, ArrowLeft, AlertCircle } from "lucide-react";
import { useSearchHighlight } from "@/hooks/useSearchHighlight";

interface MainPaneProps {
  citations: Citation[];
}

function getLegalTag(source: string) {
  if (source.includes("QH")) {
    return { label: "Luật / Nghị quyết", colorClass: "bg-red-100 text-red-700 border-red-200" };
  }
  if (source.includes("NĐ-CP") || source.includes("CP") || source.includes("TT")) {
    return { label: "Văn bản hướng dẫn", colorClass: "bg-blue-100 text-blue-700 border-blue-200" };
  }
  if (source.includes("UBND")) {
    return { label: "Văn bản địa phương", colorClass: "bg-emerald-100 text-emerald-700 border-emerald-200" };
  }
  return { label: "Tài liệu", colorClass: "bg-zinc-100 text-zinc-700 border-zinc-200" };
}

export default function MainPane({ citations }: MainPaneProps) {
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  
  const {
    activeHighlightIndex,
    highlightCount,
    loading,
    error,
    articleData,
    nextHighlight,
    prevHighlight,
    fetchArticle
  } = useSearchHighlight();

  const contentRef = useRef<HTMLDivElement>(null);

  // Parse original text to highlight what was requested.
  // The backend currently returns <b>...</b> for highlighted text, but here we can convert it to <mark>.
  const getProcessedContent = () => {
    if (!articleData) return null;
    
    // If backend provided highlighted_content, use it and convert <b> to <mark>
    if (articleData.highlighted_content) {
      // Split by <b> and </b> to create segments
      const segments = articleData.highlighted_content.split(/(<b>|<\/b>)/);
      const result = [];
      let isHighlight = false;
      let highlightIndex = 0;
      
      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (seg === "<b>") {
          isHighlight = true;
        } else if (seg === "</b>") {
          isHighlight = false;
        } else if (seg) {
          if (isHighlight) {
            const isActive = highlightIndex === activeHighlightIndex;
            result.push(
              <mark 
                key={i} 
                className={`highlight-mark ${isActive ? 'bg-amber-300 font-medium' : 'bg-amber-100'} rounded-sm px-0.5 text-zinc-900 transition-colors`}
                data-highlight-index={highlightIndex}
              >
                {seg}
              </mark>
            );
            highlightIndex++;
          } else {
            result.push(<span key={i}>{seg}</span>);
          }
        }
      }
      return result;
    }
    
    // Fallback if no highlights
    return <>{articleData.full_content}</>;
  };

  // Handle clicking a citation
  const handleSelectCitation = (citation: Citation) => {
    setSelectedCitation(citation);
    
    const query = citation.source || citation.metadata?.source || citation.metadata?.file_name?.replace(".txt", "") || "";
    fetchArticle(query, citation.text, citation.article_uuid);
  };

  // Scroll to active highlight
  useEffect(() => {
    if (contentRef.current && highlightCount > 0) {
      const marks = contentRef.current.querySelectorAll('.highlight-mark');
      if (marks.length > activeHighlightIndex) {
        const targetMark = marks[activeHighlightIndex];
        targetMark.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [activeHighlightIndex, highlightCount, articleData]);

  if (citations.length === 0) {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center text-zinc-400 p-8">
        <BookOpen size={48} className="mb-4 opacity-20" />
        <p className="text-lg font-medium text-center text-zinc-600">Chưa có Văn bản Pháp luật</p>
        <p className="text-sm text-center mt-2 max-w-sm">
          Hãy đặt một câu hỏi pháp lý ở khung bên phải để xem các tài liệu trích dẫn tương ứng tại đây.
        </p>
      </div>
    );
  }

  // View: Selected Article
  if (selectedCitation) {
    return (
      <div className="h-full flex flex-col bg-white">
        <div className="p-4 border-b border-zinc-100 bg-zinc-50/50 flex items-center gap-3">
          <button 
            onClick={() => setSelectedCitation(null)}
            className="p-1.5 rounded-md hover:bg-zinc-200 text-zinc-500 transition-colors"
            title="Quay lại danh sách"
          >
            <ArrowLeft size={18} />
          </button>
          <div className="flex-1 overflow-hidden">
            <h2 className="text-sm font-semibold text-zinc-700 truncate">
              {selectedCitation.source || selectedCitation.metadata?.file_name?.replace(".txt", "") || "Chi tiết tài liệu"}
            </h2>
            <p className="text-xs text-zinc-500 truncate">Nguyên văn điều luật</p>
          </div>
          
          {/* Navigation Controls */}
          {highlightCount > 0 && (
            <div className="flex items-center gap-2 bg-white border border-zinc-200 rounded-md px-2 py-1 shadow-sm">
              <span className="text-xs font-medium text-zinc-500 min-w-[3rem] text-center">
                {activeHighlightIndex + 1} / {highlightCount}
              </span>
              <div className="flex items-center border-l border-zinc-200 pl-1 ml-1">
                <button 
                  onClick={prevHighlight}
                  disabled={activeHighlightIndex === 0}
                  className="p-1 rounded text-zinc-500 hover:bg-zinc-100 disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft size={16} />
                </button>
                <button 
                  onClick={nextHighlight}
                  disabled={activeHighlightIndex >= highlightCount - 1}
                  className="p-1 rounded text-zinc-500 hover:bg-zinc-100 disabled:opacity-30 transition-colors"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
        
        <div className="flex-1 overflow-y-auto p-6 bg-white" ref={contentRef}>
          {loading ? (
            <div className="flex flex-col space-y-4 animate-pulse">
              <div className="h-4 bg-zinc-200 rounded w-3/4"></div>
              <div className="h-4 bg-zinc-200 rounded w-full"></div>
              <div className="h-4 bg-zinc-200 rounded w-5/6"></div>
              <div className="h-4 bg-zinc-200 rounded w-full"></div>
              <div className="h-4 bg-zinc-200 rounded w-4/5"></div>
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-100 text-red-600 rounded-lg p-4 flex flex-col items-center justify-center h-40">
              <AlertCircle size={32} className="mb-2 opacity-50" />
              <p className="text-sm font-medium">{error}</p>
              <button 
                onClick={() => {
                  const query = selectedCitation.source || selectedCitation.metadata?.source || selectedCitation.metadata?.file_name?.replace(".txt", "") || "";
                  fetchArticle(query, selectedCitation.text, selectedCitation.article_uuid);
                }}
                className="mt-3 px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-700 text-xs font-medium rounded transition-colors"
              >
                Thử lại
              </button>
            </div>
          ) : articleData ? (
            <div className="prose prose-sm max-w-none text-zinc-700 whitespace-pre-wrap leading-relaxed">
              {getProcessedContent()}
            </div>
          ) : (
            <div className="text-center py-10 text-zinc-500 text-sm italic">
              Không tìm thấy nội dung gốc.
            </div>
          )}
        </div>
      </div>
    );
  }

  // View: Citation List
  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-zinc-100 bg-zinc-50/50">
        <h2 className="text-sm font-semibold text-zinc-600 flex items-center gap-2">
          <BookOpen size={16} />
          Tài liệu tham chiếu ({citations.length} nguồn)
        </h2>
      </div>
      
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-zinc-50/30">
        {citations.map((citation, idx) => (
          <div 
            key={idx} 
            className="bg-white border border-zinc-200 rounded-lg shadow-sm overflow-hidden cursor-pointer hover:border-blue-300 hover:shadow-md transition-all"
            onClick={() => handleSelectCitation(citation)}
          >
            <div className="bg-zinc-100/50 px-4 py-3 border-b border-zinc-200 flex justify-between items-center">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-zinc-800 text-sm">
                    {citation.source || citation.metadata?.file_name?.replace(".txt", "") || "Tài liệu"}
                  </h3>
                  {citation.source && (() => {
                    const tag = getLegalTag(citation.source);
                    return (
                      <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border ${tag.colorClass}`}>
                        {tag.label}
                      </span>
                    );
                  })()}
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {citation.metadata?.part_title && (
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                      {citation.metadata.part_title}
                    </span>
                  )}
                  {citation.metadata?.chapter_title && (
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                      {citation.metadata.chapter_title}
                    </span>
                  )}
                  {citation.metadata?.article_title && (
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                      {citation.metadata.article_title}
                    </span>
                  )}
                </div>
              </div>
              <ChevronRight size={18} className="text-zinc-400" />
            </div>
            <div className="p-4 text-sm leading-relaxed text-zinc-700 whitespace-pre-wrap relative">
              <div className="line-clamp-4">
                {citation.text}
              </div>
              <div className="mt-2 text-xs font-medium text-blue-600 flex items-center gap-1">
                Xem toàn bộ văn bản gốc <ArrowLeft size={12} className="rotate-180" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
