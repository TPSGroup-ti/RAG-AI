# -*- coding: utf-8 -*-
"""
📥 RAG AI — Multi-Source Data Loader
อ่าน: เว็บ, ลิงก์, ไฟล์, API, โค้ด — ทุกแหล่งข้อมูล
"""

import re
import json
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB = True
except ImportError:
    HAS_WEB = False


class DataLoader:
    def __init__(self):
        self.session = requests.Session() if HAS_WEB else None

    def detect_source_type(self, source: str) -> str:
        """🔍 ตรวจสอบประเภทแหล่งข้อมูลอัตโนมัติ"""
        if source.startswith(("http://", "https://")):
            parsed = urlparse(source)
            if "/api/" in source or source.endswith((".json", "/api", "/graphql")):
                return "api"
            return "web"
        elif source.endswith((".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs")):
            return "code"
        elif source.endswith((".txt", ".md", ".json", ".csv")):
            return "file"
        else:
            return "text"

    def load(self, source: str, source_type: str = None) -> Tuple[str, str, Dict]:
        """📥 โหลดข้อมูลจากแหล่งที่ระบุ"""
        if not source_type:
            source_type = self.detect_source_type(source)
        
        title = "Untitled"
        content = ""
        metadata = {"source_type": source_type, "source_url": source}
        
        if source_type == "web":
            content, title = self._load_web(source)
        elif source_type == "api":
            content, metadata = self._load_api(source)
            title = f"API: {source}"
        elif source_type == "code":
            content = self._load_text(source)
            title = f"Code: {source.split('/')[-1]}"
        elif source_type == "file":
            content = self._load_text(source)
            title = f"File: {source.split('/')[-1]}"
        elif source_type == "text":
            content = source
            title = "Direct Text Input"
        
        return title, content, metadata

    def _load_web(self, url: str) -> Tuple[str, str]:
        """🌐 อ่านเนื้อหาจากหน้าเว็บ"""
        if not HAS_WEB:
            return "ต้องติดตั้ง requests และ beautifulsoup4", "ติดตั้ง: pip install requests beautifulsoup4"
        
        try:
            resp = self.session.get(url, timeout=30, headers={
                "User-Agent": "Mozilla/5.0 RAG-AI/1.0"
            })
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            # ดึงชื่อเรื่อง
            title = soup.title.string if soup.title else "Untitled Web Page"
            # ดึงเนื้อหาหลัก
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            
            paragraphs = soup.find_all(["p", "h1", "h2", "h3", "h4", "li"])
            content = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            return content.strip(), title.strip()
        except Exception as e:
            return f"Error loading page: {str(e)}", "Error"

    def _load_api(self, url: str) -> Tuple[str, Dict]:
        """🔌 ดึงข้อมูลจาก API และแปลงเป็นความรู้"""
        if not HAS_WEB:
            return "", {"error": "requests not installed"}
        
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            
            try:
                data = resp.json()
                content = json.dumps(data, ensure_ascii=False, indent=2)
                metadata = {
                    "api_url": url,
                    "response_type": "json",
                    "status_code": resp.status_code,
                    "data_preview": content[:500] + "..." if len(content) > 500 else content
                }
                return content, metadata
            except ValueError:
                return resp.text, {"api_url": url, "response_type": "text"}
        except Exception as e:
            return "", {"error": str(e), "api_url": url}

    def _load_text(self, path_or_text: str) -> str:
        """📄 อ่านไฟล์ข้อความ/โค้ด"""
        try:
            with open(path_or_text, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return path_or_text  # ถ้าไม่ใช่ไฟล์ ถือว่าเป็นข้อความตรงๆ
        except Exception as e:
            return f"Error reading: {str(e)}"

