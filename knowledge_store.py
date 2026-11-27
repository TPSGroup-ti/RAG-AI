# -*- coding: utf-8 -*-
"""
🧠 RAG AI — Personal Knowledge Base
จัดเก็บ ค้นหา และจัดการความรู้ส่วนตัวของผู้ใช้
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

class KnowledgeStore:
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.root = Path("ragai_data") / user_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.documents_path = self.root / "documents.json"
        self.chunks_path = self.root / "chunks.json"
        self.sessions_path = self.root / "sessions.json"
        self.metadata_path = self.root / "metadata.json"
        self._init_storage()

    def _init_storage(self):
        for f in [self.documents_path, self.chunks_path, self.sessions_path, self.metadata_path]:
            if not f.exists():
                self._write_json(f, []) if "session" in f.name else self._write_json(f, {})
        # Init user metadata
        if not self.metadata_path.exists() or self.metadata_path.stat().st_size == 0:
            self._write_json(self.metadata_path, {
                "user_id": self.user_id,
                "created_at": datetime.now().isoformat(),
                "total_documents": 0,
                "total_chunks": 0,
                "last_updated": None
            })

    def _read_json(self, path: Path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: Path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_document(self, source_type: str, source_url: str, title: str, content: str, metadata: Dict = None) -> str:
        """➕ เพิ่มเอกสารเข้าฐานความรู้"""
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        doc = {
            "id": doc_id,
            "type": source_type,  # web/file/api/code
            "url": source_url,
            "title": title,
            "content_preview": content[:300] + "..." if len(content) > 300 else content,
            "full_content": content,
            "metadata": metadata or {},
            "added_at": datetime.now().isoformat(),
            "chunks_count": 0
        }
        docs = self._read_json(self.documents_path)
        docs[doc_id] = doc
        self._write_json(self.documents_path, docs)
        
        # อัปเดตสถิติ
        meta = self._read_json(self.metadata_path)
        meta["total_documents"] += 1
        meta["last_updated"] = datetime.now().isoformat()
        self._write_json(self.metadata_path, meta)
        
        return doc_id

    def chunk_document(self, doc_id: str, text: str, chunk_size: int = 500) -> List[str]:
        """✂️ แบ่งเนื้อหาเป็นส่วนย่อยสำหรับค้นหา (RAG)"""
        chunks = []
        sentences = text.replace("\n", " ").split(". ")
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # บันทึกชิ้นส่วน
        chunk_data = self._read_json(self.chunks_path)
        for i, chunk_text in enumerate(chunks):
            chunk_id = f"chk_{uuid.uuid4().hex[:10]}"
            chunk_data[chunk_id] = {
                "id": chunk_id,
                "doc_id": doc_id,
                "text": chunk_text,
                "index": i
            }
        self._write_json(self.chunks_path, chunk_data)
        
        # อัปเดตจำนวนชิ้น
        docs = self._read_json(self.documents_path)
        if doc_id in docs:
            docs[doc_id]["chunks_count"] = len(chunks)
            self._write_json(self.documents_path, docs)
        
        meta = self._read_json(self.metadata_path)
        meta["total_chunks"] += len(chunks)
        self._write_json(self.metadata_path, meta)
        
        return chunks

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """🔍 ค้นหาความรู้ที่เกี่ยวข้อง (RAG Retrieval)"""
        chunks = self._read_json(self.chunks_path)
        docs = self._read_json(self.documents_path)
        query_terms = set(query.lower().split())
        
        results = []
        for chunk_id, chunk in chunks.items():
            score = 0
            chunk_text = chunk["text"].lower()
            for term in query_terms:
                if term in chunk_text:
                    score += 1
            if score > 0:
                doc_info = docs.get(chunk["doc_id"], {})
                results.append({
                    "chunk_id": chunk_id,
                    "doc_id": chunk["doc_id"],
                    "title": doc_info.get("title", "ไม่มีชื่อ"),
                    "source_type": doc_info.get("type", "unknown"),
                    "text": chunk["text"],
                    "relevance_score": score
                })
        
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:limit]

    def list_documents(self):
        """📋 รายการเอกสารทั้งหมด"""
        docs = self._read_json(self.documents_path)
        return [
            {
                "id": doc_id,
                "title": doc["title"],
                "type": doc["type"],
                "added_at": doc["added_at"],
                "chunks_count": doc["chunks_count"]
            }
            for doc_id, doc in docs.items()
        ]

    def get_stats(self):
        """📊 สถิติความรู้ของผู้ใช้"""
        return self._read_json(self.metadata_path)

    def save_session(self, query: str, answer: str, sources: List[Dict] = None):
        """💾 บันทึกการสนทนา"""
        sessions = self._read_json(self.sessions_path)
        session_id = f"ses_{uuid.uuid4().hex[:12]}"
        sessions.append({
            "id": session_id,
            "query": query,
            "answer": answer,
            "sources": sources or [],
            "timestamp": datetime.now().isoformat()
        })
        self._write_json(self.sessions_path, sessions[-100:])  # เก็บล่าสุด 100 คำถาม
        return session_id

    def export_knowledge(self, format: str = "json") -> Dict:
        """📤 ส่งออกความรู้ทั้งหมด — เพื่อนำไปใช้ในอนาคต"""
        return {
            "metadata": self._read_json(self.metadata_path),
            "documents": self._read_json(self.documents_path),
            "chunks": self._read_json(self.chunks_path),
            "sessions": self._read_json(self.sessions_path),
            "exported_at": datetime.now().isoformat(),
            "format_version": "1.0"
        }

    def import_knowledge(self, data: Dict) -> bool:
        """📥 นำเข้าฐานความรู้ที่เคยส่งออก"""
        try:
            if "documents" in data:
                existing = self._read_json(self.documents_path)
                merged = {**existing, **data["documents"]}
                self._write_json(self.documents_path, merged)
            if "chunks" in data:
                existing = self._read_json(self.chunks_path)
                merged = {**existing, **data["chunks"]}
                self._write_json(self.chunks_path, merged)
            # อัปเดตสถิติ
            docs = self._read_json(self.documents_path)
            chunks = self._read_json(self.chunks_path)
            meta = self._read_json(self.metadata_path)
            meta["total_documents"] = len(docs)
            meta["total_chunks"] = len(chunks)
            meta["last_updated"] = datetime.now().isoformat()
            self._write_json(self.metadata_path, meta)
            return True
        except Exception:
            return False

