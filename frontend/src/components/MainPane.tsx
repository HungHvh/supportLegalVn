import { Citation } from "@/app/page";
import { BookOpen } from "lucide-react";

interface MainPaneProps {
  citations: Citation[];
}

export default function MainPane({ citations }: MainPaneProps) {
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
          <div key={idx} className="bg-white border border-zinc-200 rounded-lg shadow-sm overflow-hidden">
            <div className="bg-zinc-100/50 px-4 py-3 border-b border-zinc-200">
              <h3 className="font-semibold text-zinc-800 text-sm">
                {citation.metadata.file_name.replace(".txt", "")}
              </h3>
              <div className="flex flex-wrap gap-2 mt-2">
                {citation.metadata.part_title && (
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                    {citation.metadata.part_title}
                  </span>
                )}
                {citation.metadata.chapter_title && (
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                    {citation.metadata.chapter_title}
                  </span>
                )}
                {citation.metadata.article_title && (
                  <span className="text-[10px] uppercase tracking-wider font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                    {citation.metadata.article_title}
                  </span>
                )}
              </div>
            </div>
            <div className="p-4 text-sm leading-relaxed text-zinc-700 whitespace-pre-wrap">
              {citation.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
