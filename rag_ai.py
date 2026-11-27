# -*- coding: utf-8 -*-
"""
🧠 RAG AI — Personal Knowledge Engine | All-in-One Edition
📦 Version: 1.0.0 — Single File
👤 Creator: Thanwa Phupingbut | Rufio D'noto
🏷️ Brand: TPS Group
🔗 GitHub: https://github.com/TPSGroup-ti/RAG-AI

✅ ความสามารถ:
   🌐 อ่านเว็บ/ลิงก์ · 📄 อ่านไฟล์/โค้ด · 🔌 อ่าน API
   🧠 จัดเก็บแบบ RAG · 🔍 ค้นหาความรู้ · 🤖 ถาม-ตอบ
   📤 ส่งออกความรู้ · 📥 นำเข้าความรู้ · 🔑 แยกผู้ใช้ด้วย Token
"""

import json
import uuid
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Header, Body, Depends
from fastapi.middleware.cors import CORSMiddleware

# ==========================================
# 🧠 KNOWLEDGE STORE — ฐานความรู้ส่วนตัว
# ==========================================

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
                self._write_json(f, {} if "doc" in f.name or "chunk" in f.name or "meta" in f.name else [])
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
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        doc = {
            "id": doc_id,
            "type": source_type,
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
        
        meta = self._read_json(self.metadata_path)
        meta["total_documents"] += 1
        meta["last_updated"] = datetime.now().isoformat()
        self._write_json(self.metadata_path, meta)
        return doc_id

    def chunk_document(self, doc_id: str, text: str, chunk_size: int = 500) -> List[str]:
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
        
        chunk_data = self._read_json(self.chunks_path)
        for i, chunk_text in enumerate(chunks):
            chunk_id = f"chk_{uuid.uuid4().hex[:10]}"
            chunk_data[chunk_id] = {"id": chunk_id, "doc_id": doc_id, "text": chunk_text, "index": i}
        self._write_json(self.chunks_path, chunk_data)
        
        docs = self._read_json(self.documents_path)
        if doc_id in docs:
            docs[doc_id]["chunks_count"] = len(chunks)
            self._write_json(self.documents_path, docs)
        
        meta = self._read_json(self.metadata_path)
        meta["total_chunks"] += len(chunks)
        self._write_json(self.metadata_path, meta)
        return chunks

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        chunks = self._read_json(self.chunks_path)
        docs = self._read_json(self.documents_path)
        query_terms = set(query.lower().split())
        results = []
        for chunk_id, chunk in chunks.items():
            score = sum(1 for term in query_terms if term in chunk["text"].lower())
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
        docs = self._read_json(self.documents_path)
        return [{"id": d_id, **{k:v for k,v in doc.items() if k != "full_content"}} for d_id, doc in docs.items()]

    def get_stats(self):
        return self._read_json(self.metadata_path)

    def save_session(self, query: str, answer: str, sources: List[Dict] = None):
        sessions = self._read_json(self.sessions_path)
        sessions.append({
            "id": f"ses_{uuid.uuid4().hex[:12]}",
            "query": query,
            "answer": answer,
            "sources": sources or [],
            "timestamp": datetime.now().isoformat()
        })
        self._write_json(self.sessions_path, sessions[-100:])

    def export_knowledge(self) -> Dict:
        return {
            "metadata": self._read_json(self.metadata_path),
            "documents": self._read_json(self.documents_path),
            "chunks": self._read_json(self.chunks_path),
            "sessions": self._read_json(self.sessions_path),
            "exported_at": datetime.now().isoformat(),
            "format_version": "1.0"
        }

    def import_knowledge(self, data: Dict) -> bool:
        try:
            if "documents" in data:
                existing = self._read_json(self.documents_path)
                self._write_json(self.documents_path, {**existing, **data["documents"]})
            if "chunks" in data:
                existing = self._read_json(self.chunks_path)
                self._write_json(self.chunks_path, {**existing, **data["chunks"]})
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

# ==========================================
# 📥 DATA LOADER — อ่านทุกแหล่งข้อมูล
# ==========================================

class DataLoader:
    def __init__(self):
        self.session = requests.Session() if HAS_WEB else None

    def detect_source_type(self, source: str) -> str:
        if source.startswith(("http://", "https://")):
            return "api" if "/api/" in source or source.endswith((".json", "/api")) else "web"
        elif source.endswith((".py", ".js", ".html", ".css", ".java", ".cpp", ".go", ".rs")):
            return "code"
        elif source.endswith((".txt", ".md", ".json", ".csv")):
            return "file"
        return "text"

    def load(self, source: str, source_type: str = None) -> Tuple[str, str, Dict]:
        if not source_type:
            source_type = self.detect_source_type(source)
        title = "Untitled"
        content = ""
        metadata = {"source_type": source_type, "source_url": source}
        
        if source_type == "web":
            content, title = self._load_web(source)
        elif source_type == "api":
            content, meta = self._load_api(source)
            metadata.update(meta)
            title = f"API: {source}"
        elif source_type in ["code", "file"]:
            content = self._load_text(source)
            title = f"{source_type.capitalize()}: {source.split('/')[-1]}"
        else:
            content = source
            title = "Direct Text Input"
        return title, content, metadata

    def _load_web(self, url: str) -> Tuple[str, str]:
        if not HAS_WEB:
            return "ต้องติดตั้ง requests beautifulsoup4", "Missing Dependencies"
        try:
            resp = self.session.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 RAG-AI/1.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.title.string.strip() if soup.title else "Untitled Web Page"
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            paragraphs = soup.find_all(["p", "h1", "h2", "h3", "h4", "li"])
            content = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            return content.strip(), title
        except Exception as e:
            return f"Error: {str(e)}", "Error"

    def _load_api(self, url: str) -> Tuple[str, Dict]:
        if not HAS_WEB:
            return "", {"error": "requests not installed"}
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            try:
                data = resp.json()
                return json.dumps(data, ensure_ascii=False, indent=2), {
                    "api_url": url, "response_type": "json", "status_code": resp.status_code
                }
            except ValueError:
                return resp.text, {"api_url": url, "response_type": "text"}
        except Exception as e:
            return "", {"error": str(e), "api_url": url}

    def _load_text(self, path_or_text: str) -> str:
        try:
            with open(path_or_text, "r", encoding="utf-8") as f:
                return f.read()
        except (FileNotFoundError, OSError):
            return path_or_text
        except Exception as e:
            return f"Error: {str(e)}"

# ==========================================
# 🔐 USER MANAGEMENT
# ==========================================

class UserManager:
    def __init__(self):
        self.users: Dict[str, Dict] = {}
    
    def get_or_create(self, token: str) -> KnowledgeStore:
        if token not in self.users:
            self.users[token] = {
                "user_id": f"usr_{uuid.uuid4().hex[:12]}",
                "created_at": datetime.now().isoformat(),
                "store": KnowledgeStore(token)
            }
        return self.users[token]["store"]

user_manager = UserManager()
data_loader = DataLoader()

# ==========================================
# 📋 DATA MODELS
# ==========================================

class LoadSourceRequest(BaseModel):
    source: str
    source_type: Optional[str] = None

class QueryRequest(BaseModel):
    question: str
    top_k: int = 5

class FeedbackRequest(BaseModel):
    answer: str
    is_correct: bool
    correction: Optional[str] = None

# ==========================================
# 🚀 FASTAPI APP
# ==========================================

app = FastAPI(
    title="🧠 RAG AI — Personal Knowledge Engine",
    description="อ่านเว็บ · ไฟล์ · API · โค้ด → สร้างความรู้ส่วนตัว → ถามตอบ → ส่งออกได้ตลอด",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_store(x_user_token: str = Header(..., description="Token ส่วนตัวของคุณ")):
    return user_manager.get_or_create(x_user_token)

# ==========================================
# 🏠 HOME
# ==========================================

@app.get("/")
def home():
    return {
        "system": "🧠 RAG AI — Personal Knowledge Engine",
        "version": "1.0.0",
        "status": "✅ ONLINE",
        "github": "https://github.com/TPSGroup-ti/RAG-AI",
        "note": "ส่ง Header: X-User-Token: <รหัสส่วนตัว> เพื่อเริ่มใช้งาน",
        "endpoints": {
            "➕ เพิ่มความรู้": "POST /knowledge/add",
            "📋 รายการ": "GET /knowledge/list",
            "🔍 ค้นหา": "POST /knowledge/search",
            "❓ ถามคำถาม": "POST /ai/ask",
            "✅ ให้ข้อมูลย้อนกลับ": "POST /ai/feedback",
            "📤 ส่งออก": "GET /knowledge/export",
            "📥 นำเข้า": "POST /knowledge/import",
            "📊 สถิติ": "GET /stats",
            "📖 เอกสาร": "/docs"
        }
    }

# ==========================================
# 📥 KNOWLEDGE ENDPOINTS
# ==========================================

@app.post("/knowledge/add")
def add_knowledge(req: LoadSourceRequest, store: KnowledgeStore = Depends(get_store)):
    title, content, meta = data_loader.load(req.source, req.source_type)
    if not content or content.startswith("Error"):
        raise HTTPException(400, f"โหลดข้อมูลไม่สำเร็จ: {content}")
    doc_id = store.add_document(meta["source_type"], req.source, title, content, meta)
    chunks = store.chunk_document(doc_id, content)
    return {
        "ok": True,
        "message": f"✅ เพิ่มสำเร็จ: {title}",
        "document_id": doc_id,
        "chunks": len(chunks),
        "preview": content[:200] + "..." if len(content) > 200 else content
    }

@app.get("/knowledge/list")
def list_knowledge(store: KnowledgeStore = Depends(get_store)):
    return {"documents": store.list_documents()}

@app.delete("/knowledge/{doc_id}")
def remove_knowledge(doc_id: str, store: KnowledgeStore = Depends(get_store)):
    docs = store._read_json(store.documents_path)
    if doc_id not in docs:
        raise HTTPException(404, "ไม่พบเอกสาร")
    del docs[doc_id]
    store._write_json(store.documents_path, docs)
    return {"ok": True, "message": "ลบแล้ว"}

@app.post("/knowledge/search")
def search_knowledge(req: QueryRequest, store: KnowledgeStore = Depends(get_store)):
    return {"query": req.question, "results": store.search(req.question, req.top_k)}

# ==========================================
# 🤖 AI ENDPOINTS
# ==========================================

@app.post("/ai/ask")
@app.post("/ai/ask")
def ask_ai(req: QueryRequest, store: KnowledgeStore = Depends(get_store)):
    """🤖 ถามคำถาม — AI ค้นหาความรู้และตอบให้"""
    results = store.search(req.question, req.top_k)
    
    if not results:
        answer = "ฉันยังไม่มีความรู้เกี่ยวกับเรื่องนี้ กรุณาเพิ่มแหล่งความรู้ก่อนครับ"
    else:
        context = "\n\n".join([f"[{r['title']}]\n{r['text']}" for r in results])
        answer = f"""พบข้อมูลที่เกี่ยวข้อง {len(results)} แหล่ง:

{context}

---
📌 จากข้อมูลข้างต้น: {req.question}
"""
    
    store.save_session(req.question, answer, results)
    return {
        "question": req.question,
        "answer": answer,
        "sources": results,
        "has_knowledge": len(results) > 0
    }

@app.post("/ai/feedback")
def feedback(fb: FeedbackRequest, store: KnowledgeStore = Depends(get_store)):
    """✅ บันทึกผลตรวจสอบคำตอบ"""
    return {
        "ok": True,
        "message": "✅ บันทึกแล้ว",
        "is_correct": fb.is_correct,
        "note": fb.correction if not fb.is_correct else "ขอบคุณครับ!"
    }

# ==========================================
# 📤 EXPORT / IMPORT
# ==========================================

@app.get("/knowledge/export")
def export_knowledge(store: KnowledgeStore = Depends(get_store)):
    """📤 ส่งออกความรู้ทั้งหมดของคุณ"""
    return {
        "ok": True,
        "exported_at": datetime.now().isoformat(),
        "data": store.export_knowledge()
    }

@app.post("/knowledge/import")
def import_knowledge(data: Dict, store: KnowledgeStore = Depends(get_store)):
    """📥 นำเข้าความรู้"""
    if store.import_knowledge(data):
        return {"ok": True, "message": "✅ นำเข้าสำเร็จ"}
    raise HTTPException(400, "รูปแบบข้อมูลไม่ถูกต้อง")

# ==========================================
# 📊 STATS & SESSIONS
# ==========================================

@app.get("/stats")
def stats(store: KnowledgeStore = Depends(get_store)):
    """📊 สถิติความรู้ของคุณ"""
    return store.get_stats()

@app.get("/sessions")
def sessions(limit: int = 20, store: KnowledgeStore = Depends(get_store)):
    """📜 ประวัติการถาม-ตอบ"""
    sessions = store._read_json(store.sessions_path)
    return {"sessions": sessions[-limit:]}

# ==========================================
# 🚀 RUN SERVER
# ==========================================

if __name__ == "__main__":
    import uvicorn
    import os
    PORT = int(os.getenv("PORT", 8130))
    print(f"""
{'='*60}
🧠 RAG AI — Personal Knowledge Engine | All-in-One
{'='*60}
✅ ไฟล์เดียวครบจบ! พร้อมใช้งานทันที

🌐 หน้าหลัก:    http://127.0.0.1:{PORT}
📖 API Docs:    http://127.0.0.1:{PORT}/docs
📂 ข้อมูลที่:   ./ragai_data/

🔑 วิธีใช้งาน:
   1️⃣ ติดตั้ง: pip install fastapi uvicorn pydantic requests beautifulsoup4
   2️⃣ รัน:     python rag_ai.py
   3️⃣ Header:  X-User-Token: <รหัสส่วนตัวของคุณ>

💎 Creator: Thanwa Phupingbut | Rufio D'noto
🏷️ Brand: TPS Group
🔗 GitHub: https://github.com/TPSGroup-ti/RAG-AI
{'='*60}
""")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
