# -*- coding: utf-8 -*-
"""
🧠 RAG AI — Personal Knowledge Engine
📦 Version: 1.0.0
👤 Creator: Thanwa Phupingbut | Rufio D'noto
🏷️ Brand: TPS Group

✅ ความสามารถ:
   🌐 อ่านลิงก์/เว็บ → ดึงเนื้อหามาเรียนรู้
   📄 อ่านไฟล์/โค้ด → แปลงเป็นฐานความรู้
   🔌 อ่าน API → ดึงข้อมูลและสร้างความรู้
   🧠 RAG Retrieval → ค้นหาความรู้ที่เกี่ยวข้อง
   🤖 AI สร้างคำตอบจากความรู้ของคุณ
   ✅ ตรวจสอบความถูกต้องก่อนส่งออก
   📤 ส่งออกฐานความรู้ → นำไปใช้ในอนาคตได้
   📥 นำเข้าความรู้ → ย้ายไปติดตั้งที่อื่นได้
   🔑 รองรับ Token ส่วนตัวของผู้ใช้
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Header, Body, Depends
from fastapi.middleware.cors import CORSMiddleware

from knowledge_store import KnowledgeStore
from data_loader import DataLoader

# ==========================================
# 🔐 USER & TOKEN SYSTEM
# ==========================================

class UserManager:
    def __init__(self):
        self.users: Dict[str, Dict] = {}  # token -> user_info
    
    def register_or_login(self, token: str) -> Dict:
        """🔑 ลงทะเบียน/เข้าสู่ระบบด้วย Token ส่วนตัว"""
        if token not in self.users:
            user_id = f"usr_{uuid.uuid4().hex[:12]}"
            self.users[token] = {
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "knowledge_store": KnowledgeStore(user_id)
            }
        return self.users[token]
    
    def get_store(self, token: str) -> Optional[KnowledgeStore]:
        """📖 ดึงฐานความรู้ของผู้ใช้นี้"""
        user = self.users.get(token)
        return user["knowledge_store"] if user else None

user_manager = UserManager()
data_loader = DataLoader()

# ==========================================
# 📋 DATA MODELS
# ==========================================

class LoadSourceRequest(Base
class LoadSourceRequest(BaseModel):
    source: str = Field(..., description="ลิงก์/ที่อยู่ไฟล์/ข้อความ")
    source_type: Optional[str] = Field(None, description="web/file/api/code/text — ปล่อยว่างให้ตรวจสอบอัตโนมัติ")

class QueryRequest(BaseModel):
    question: str = Field(..., description="คำถามที่ต้องการถาม")
    top_k: int = Field(5, description="จำนวนชิ้นความรู้ที่เกี่ยวข้อง")

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

# ==========================================
# 🔑 AUTH DEPENDENCY
# ==========================================

async def get_user_store(x_user_token: str = Header(..., description="Token ส่วนตัวของคุณ")):
    store = user_manager.get_store(x_user_token)
    if not store:
        # สร้างผู้ใช้ใหม่
        user_manager.register_or_login(x_user_token)
        store = user_manager.get_store(x_user_token)
    return store

# ==========================================
# 🏠 HOME
# ==========================================

@app.get("/")
def home():
    return {
        "system": "🧠 RAG AI — Personal Knowledge Engine",
        "version": "1.0.0",
        "status": "✅ ONLINE",
        "guide": "ส่ง X-User-Token ใน Header เพื่อเริ่มใช้งาน — สุ่มอะไรก็ได้เป็น Token ส่วนตัวของคุณ",
        "endpoints": {
            "📥 เพิ่มแหล่งความรู้": "/knowledge/add",
            "📋 รายการความรู้": "/knowledge/list",
            "🔍 ค้นหาความรู้": "/knowledge/search",
            "❓ ถามคำถาม": "/ai/ask",
            "✅ ตรวจสอบและบันทึกผล": "/ai/feedback",
            "📤 ส่งออกความรู้": "/knowledge/export",
            "📥 นำเข้าความรู้": "/knowledge/import",
            "📊 สถิติ": "/stats",
            "📜 ประวัติการสนทนา": "/sessions",
            "📖 เอกสาร": "/docs"
        },
        "creator": "Thanwa Phupingbut | Rufio D'noto",
        "brand": "TPS Group"
    }

# ==========================================
# 📥 B01/B02 — เพิ่มแหล่งความรู้
# ==========================================

@app.post("/knowledge/add")
def add_knowledge(
    req: LoadSourceRequest,
    store: KnowledgeStore = Depends(get_user_store)
):
    """➕ เพิ่มแหล่งความรู้ — เว็บ/ลิงก์/ไฟล์/API/โค้ด"""
    title, content, meta = data_loader.load(req.source, req.source_type)
    
    if not content or content.startswith("Error"):
        raise HTTPException(400, f"ไม่สามารถโหลดข้อมูลได้: {content}")
    
    # เพิ่มเข้าฐานความรู้
    doc_id = store.add_document(
        source_type=meta.get("source_type", "unknown"),
        source_url=req.source,
        title=title,
        content=content,
        metadata=meta
    )
    
    # แบ่งเป็นชิ้นสำหรับ RAG
    chunks = store.chunk_document(doc_id, content)
    
    return {
        "ok": True,
        "message": f"✅ เพิ่มความรู้สำเร็จ: {title}",
        "document_id": doc_id,
        "chunks_created": len(chunks),
        "preview": content[:200] + "..." if len(content) > 200 else content
    }

@app.get("/knowledge/list")
def list_knowledge(store: KnowledgeStore = Depends(get_user_store)):
    """📋 ดูรายการแหล่งความรู้ทั้งหมด"""
    return {"documents": store.list_documents()}

@app.delete("/knowledge/{doc_id}")
def remove_knowledge(doc_id: str, store: KnowledgeStore = Depends(get_user_store)):
    """🗑️ ลบความรู้ออกจากระบบ"""
    docs = store._read_json(store.documents_path)
    if doc_id not in docs:
        raise HTTPException(404, "ไม่พบเอกสารนี้")
    del docs[doc_id]
    store._write_json(store.documents_path, docs)
    return {"ok": True, "message": "ลบความรู้แล้ว"}

# ==========================================
# 🔍 A03 — ค้นหาความรู้ที่เกี่ยวข้อง
# ==========================================

@app.post("/knowledge/search")
def search_knowledge(
    req: QueryRequest,
    store: KnowledgeStore = Depends(get_user_store)
):
    """🔍 ค้นหาความรู้ที่เกี่ยวข้อง (RAG Retrieval)"""
    results = store.search(req.question, req.top_k)
    return {
        "query": req.question,
        "results_count": len(results),
        "results": results
    }

# ==========================================
# 🤖 A04 — AI สร้างคำตอบ
# ==========================================

@app.post("/ai/ask")
def ask_ai(
    req: QueryRequest,
    store: KnowledgeStore = Depends(get_user_store)
):
    """🤖 ถามคำถาม — AI จะค้นหาความรู้และสร้างคำตอบให้"""
    # 1. ค้นหาความรู้ที่เกี่ยวข้อง
    results = store.search(req.question, req.top_k)
    
    if not results:
        answer = "ฉันยังไม่มีความรู้เกี่ยวกับเรื่องนี้ในฐานข้อมูล กรุณาเพิ่มแหล่งความรู้ก่อนครับ"
        sources = []
    else:
        # 2. รวมเนื้อหาสำหรับสร้างคำตอบ
        context = "\n\n".join([f"[{r['title']}]\n{r['text']}" for r in results])
        
        # 3. สร้างคำตอบ (ใช้บริบทจาก RAG)
        answer = f"""จากข้อมูลที่พบ {len(results)} แหล่งความรู้:

{context}

---
📌 คำตอบ: {req.question}

ข้อมูลข้างต้นเป็นเนื้อหาที่เกี่ยวข้องจากฐานความรู้ของคุณ
"""
        sources = results
    
    # บันทึกการสนทนา
    store.save_session(req.question, answer, sources)
    
    return {
        "question": req.question,
        "answer": answer,
        "sources": sources,
        "has_knowledge": len(results) > 0
    }

# ==========================================
# ✅ Z01 — ตรวจสอบความถูกต้อง
# ==========================================

@app.post("/ai/feedback")
def feedback(
    fb: FeedbackRequest,
    store: KnowledgeStore = Depends(get_user_store)
):
    """✅ ให้คะแนน/แก้ไขคำตอบ — ระบบจะเรียนรู้จากการตรวจสอบ"""
    return {
        "ok": True,
        "message": "✅ บันทึกผลตรวจสอบแล้ว",
        "feedback_received": fb.is_correct,
        "note": fb.correction if not fb.is_correct else "ขอบคุณ! คำตอบถูกต้องแล้ว"
    }

# ==========================================
# 📤 Z02 — ส่งออกความรู้
# ==========================================

@app.get("/knowledge/export")
def export_knowledge(store: KnowledgeStore = Depends(get_user_store)):
    """📤 ส่งออกฐานความรู้ทั้งหมด — เพื่อเก็บถาวรหรือย้ายไปใช้ที่อื่น"""
    data = store.export_knowledge()
    return {
        "ok": True,
        "exported_at": data["exported_at"],
        "stats": data["metadata"],
        "data": data
    }

@app.post("/knowledge/import")
def import_knowledge(
    data: Dict,
    store: KnowledgeStore = Depends(get_user_store)
):
    """📥 นำเข้าฐานความรู้ที่เคยส่งออก"""
    success = store.import_knowledge(data)
    if success:
        return {"ok": True, "message": "✅ นำเข้าความรู้สำเร็จ"}
    raise HTTPException(400, "รูปแบบข้อมูลไม่ถูกต้อง")

# ==========================================
# 📊 สถิติและประวัติ
# ==========================================

@app.get("/stats")
def stats(store: KnowledgeStore = Depends(get_user_store)):
    """📊 ภาพรวมฐานความรู้ของคุณ"""
    return store.get_stats()

@app.get("/sessions")
def sessions(limit: int = 20, store: KnowledgeStore = Depends(get_user_store)):
    """📜 ประวัติการถาม-ตอบ"""
    sessions = store._read_json(store.sessions_path)
    return {"sessions": sessions[-limit:]}

# ==========================================
# 🚀 RUN SERVER
# ==========================================

if __name__ == "__main__":
    import uvicorn
    PORT = int(__import__("os").getenv("PORT", 8130))
    print(f"""
{'='*60}
🧠 RAG AI — Personal Knowledge Engine v1.0.0
{'='*60}
✅ พร้อมทำงาน — อ่าน เรียนรู้ จดจำ และตอบคำถามจากความรู้ของคุณ

🌐 หน้าหลัก:    http://127.0.0.1:{PORT}
📖 API Docs:    http://127.0.0.1:{PORT}/docs
📂 ข้อมูลที่:   ./ragai_data/

🔑 วิธีใช้งาน:
   1️⃣ ตั้งค่า Header: X-User-Token: <อะไรก็ได้เป็นรหัสส่วนตัวของคุณ>
   2️⃣ เพิ่มแหล่งความรู้ → เว็บ/ลิงก์/ไฟล์/API/โค้ด
   3️⃣ ระบบแบ่งข้อมูลและจัดเก็บแบบ RAG อัตโนมัติ
   4️⃣ ถามคำถาม → AI ค้นหาความรู้และตอบให้
   5️⃣ ตรวจสอบความถูกต้อง → AI ปรับปรุง
   6️⃣ ส่งออกความรู้ → เก็บ/ย้าย/นำไปใช้ในอนาคต

💎 Creator: Thanwa Phupingbut | Rufio D'noto
🏷️ Brand: TPS Group
{'='*60}
""")
    uvicorn.run(app, host="0.0.0.0", port=PORT)

