import re
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class LegalLevel(str, Enum):
    DOCUMENT = "DOCUMENT"
    PART = "PHẦN"
    CHAPTER = "CHƯƠNG"
    SECTION = "MỤC"
    ARTICLE = "ĐIỀU"
    CLAUSE = "KHOẢN"
    POINT = "ĐIỂM"

class LegalNode(BaseModel):
    level: LegalLevel
    title: str
    content: str = ""
    full_path: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    children: List["LegalNode"] = Field(default_factory=list)

LegalNode.model_rebuild()

class VietnameseLegalParser:
    """Specialized parser for Vietnamese legal documents structure."""
    
    PATTERNS = {
        LegalLevel.PART: r'^Phần\s+.*?\.',
        LegalLevel.CHAPTER: r'^Chương\s+.*?\.',
        LegalLevel.SECTION: r'^Mục\s+\d+.*?\.',
        LegalLevel.ARTICLE: r'^Điều\s+\d+.*?\.',
        LegalLevel.CLAUSE: r'^\d+\.',
        LegalLevel.POINT: r'^[a-z]\)'
    }

    def __init__(self):
        self.re_flags = re.MULTILINE | re.IGNORECASE

    def split_text(self, text: str, level: LegalLevel) -> List[Dict[str, str]]:
        """Splits text by a specific legal level pattern."""
        pattern = self.PATTERNS.get(level)
        if not pattern:
            return [{"title": "", "content": text}]
            
        matches = list(re.finditer(pattern, text, self.re_flags))
        if not matches:
            return [{"title": "", "content": text}]
            
        results = []
        for i, match in enumerate(matches):
            title = match.group(0).strip()
            start = match.end()
            end = matches[i+1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            results.append({"title": title, "content": content})
            
        # Handle preamble (text before the first match)
        if matches[0].start() > 0:
            preamble = text[0:matches[0].start()].strip()
            if preamble:
                results.insert(0, {"title": "PREAMBLE", "content": preamble})
                
        return results

    def parse_recursive(self, text: str, levels: List[LegalLevel], parent_path: str = "") -> List[LegalNode]:
        """Recursively parses text into a tree of LegalNodes."""
        if not levels or not text.strip():
            return []
            
        current_level = levels[0]
        remaining_levels = levels[1:]
        
        pattern = self.PATTERNS.get(current_level)
        matches = list(re.finditer(pattern, text, self.re_flags)) if pattern else []
        
        # If this level doesn't exist in the text, skip to the next level
        if not matches:
            return self.parse_recursive(text, remaining_levels, parent_path)
            
        splits = self.split_text(text, current_level)
        nodes = []
        
        for split in splits:
            title = split["title"]
            content = split["content"]
            
            # Construct full path for context injection
            current_path = f"{parent_path} > {title}" if parent_path and title != "PREAMBLE" else title
            if title == "PREAMBLE":
                current_path = parent_path # Don't add PREAMBLE to path
            
            node = LegalNode(
                level=current_level,
                title=title,
                content=content,
                full_path=current_path
            )
            
            # Recurse if there's content and more levels
            if content and remaining_levels:
                node.children = self.parse_recursive(content, remaining_levels, current_path)
                
            nodes.append(node)
            
        return nodes

    def parse_document(self, text: str, law_name: str = "") -> LegalNode:
        """Entry point for parsing a full legal document."""
        levels = [
            LegalLevel.PART, 
            LegalLevel.CHAPTER, 
            LegalLevel.SECTION, 
            LegalLevel.ARTICLE, 
            LegalLevel.CLAUSE, 
            LegalLevel.POINT
        ]
        
        root = LegalNode(
            level=LegalLevel.DOCUMENT,
            title=law_name,
            full_path=law_name
        )
        
        root.children = self.parse_recursive(text, levels, law_name)
        return root
