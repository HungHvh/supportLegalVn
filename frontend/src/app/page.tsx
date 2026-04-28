"use client";

import { useState } from "react";
import MainPane from "@/components/MainPane";
import ChatSidebar from "@/components/ChatSidebar";

export interface Citation {
  text: string;
  metadata: {
    source: string;
    file_name: string;
    article_title?: string;
    chapter_title?: string;
    part_title?: string;
  };
}

export interface Message {
  role: "user" | "agent";
  content: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const handleSendMessage = async (content: string) => {
    const newMessages = [...messages, { role: "user", content } as Message];
    setMessages(newMessages);
    setIsLoading(true);

    try {
      const response = await fetch("http://localhost:8000/api/v1/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: content }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch");
      }

      const data = await response.json();
      
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: data.answer },
      ]);
      setCitations(data.citations || []);
    } catch (error) {
      console.error(error);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: "Lỗi kết nối đến máy chủ. Vui lòng đảm bảo Backend đang chạy ở cổng 8000." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full bg-zinc-50 overflow-hidden font-sans">
      {/* Left Pane - Context Retrieval */}
      <div className="w-1/2 h-full border-r border-zinc-200 bg-white">
        <MainPane citations={citations} />
      </div>

      {/* Right Pane - Chat Interface */}
      <div className="w-1/2 h-full bg-zinc-50 flex flex-col">
        <ChatSidebar 
          messages={messages} 
          onSendMessage={handleSendMessage} 
          isLoading={isLoading} 
        />
      </div>
    </div>
  );
}
