#!/usr/bin/env python3
import os
import sys
import json
import asyncio
import psycopg2
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

# Load env from the shared project locations first so runtime matches the
# same credential surface used by the web server, OpenHands, and Cursor config.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
for env_path in [PROJECT_ROOT / ".env", PROJECT_ROOT / "mcp-unified" / ".env"]:
    if env_path.exists():
        load_dotenv(env_path, override=False)

# Preserve local overrides as the last fallback.
load_dotenv(override=False)

# Configure logging to stderr for MCP to keep stdout for protocol
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("korespondensi-server")

class KorespondensiMCP:
    def __init__(self):
        self.server = Server("korespondensi-server")
        self._setup_tools()

    def _get_db_connection(self):
        """Establish connection to mcp_knowledge database."""
        try:
            return psycopg2.connect(
                host=os.getenv("PG_HOST", "localhost"),
                port=os.getenv("PG_PORT", "5433"),
                database=os.getenv("PG_DATABASE", "mcp_knowledge"),
                user=os.getenv("PG_USER", "mcp_user"),
                password=os.getenv("PG_PASSWORD", "mcp_password_2024")
            )
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def _setup_tools(self):
        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            return [
                Tool(
                    name="cari_surat",
                    description="Mencari data surat masuk/keluar berdasarkan nomor atau perihal secara global di seluruh unit.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Nomor surat, judul, atau perihal yang dicari."},
                            "limit": {"type": "integer", "description": "Jumlah maksimal hasil.", "default": 5}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="status_disposisi",
                    description="Mengecek status dan posisi terakhir surat (timeline) dari database pusat korespondensi.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "no_surat": {"type": "string", "description": "Nomor surat atau nomor agenda surat."},
                        },
                        "required": ["no_surat"]
                    }
                ),
                Tool(
                    name="kirim_reminder",
                    description="Kirim pengingat tindak lanjut via Telegram Admin PUU untuk surat yang belum selesai diproses.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "no_surat": {"type": "string", "description": "Nomor surat yang ingin diproses."},
                            "pesan": {"type": "string", "description": "Pesan khusus pengingat (misal: 'Mohon dicek kembali di SUPD II')."}
                        },
                        "required": ["no_surat"]
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
            try:
                if name == "cari_surat":
                    return await self.tool_cari_surat(arguments["query"], arguments.get("limit", 5))
                elif name == "status_disposisi":
                    return await self.tool_status_disposisi(arguments["no_surat"])
                elif name == "kirim_reminder":
                    return await self.tool_kirim_reminder(arguments["no_surat"], arguments.get("pesan", ""))
                else:
                    raise ValueError(f"Tool {name} tidak ditemukan.")
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

    async def tool_cari_surat(self, query: str, limit: int) -> list[TextContent]:
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cur:
                # Search across pool for maximum reach
                sql = """
                    SELECT source_sheet_name as tipe, nomor_nd, hal, dari, posisi, update_date 
                    FROM (
                        SELECT source_sheet_name, nomor_nd, hal, dari, posisi, updated_at as update_date
                        FROM korespondensi_raw_pool 
                        WHERE (nomor_nd ILIKE %s OR hal ILIKE %s OR disposisi ILIKE %s)
                    ) sub
                    ORDER BY update_date DESC LIMIT %s
                """
                pattern = f"%{query}%"
                cur.execute(sql, (pattern, pattern, pattern, limit))
                rows = cur.fetchall()
                
                if not rows:
                    return [TextContent(type="text", text=f"🔍 Tidak ditemukan surat dengan query: '{query}'")]
                
                results = []
                for i, r in enumerate(rows, 1):
                    results.append(f"{i}. [{r[0]}] No: {r[1]}\n   📝 Hal: {r[2][:120]}...\n   📍 Posisi: {r[4] or '-'}")
                
                return [TextContent(type="text", text="\n\n".join(results))]
        finally:
            conn.close()

    async def tool_status_disposisi(self, no_surat: str) -> list[TextContent]:
        conn = self._get_db_connection()
        try:
            with conn.cursor() as cur:
                # Search in raw pool
                cur.execute("""
                    SELECT nomor_nd, posisi, disposisi, dari, hal 
                    FROM korespondensi_raw_pool 
                    WHERE nomor_nd ILIKE %s LIMIT 1
                """, (f"%{no_surat}%",))
                
                row = cur.fetchone()
                if not row:
                    return [TextContent(type="text", text=f"❌ Surat '{no_surat}' tidak ditemukan di database pusat.")]
                
                nomor_nd = row[0]
                raw_posisi = row[1] or ""
                dispo = row[2] or "-"
                from_unit = row[3] or "-"
                hal = row[4] or "-"
                
                # Regex for timeline parsing (SES 9/3 PUU 11/3)
                events = re.findall(r'([A-Z\d\.\s]+)\s+(\d{1,2}/\d{1,2})', raw_posisi)
                timeline = "\n".join([f"   🗓️ {ev[1]} : Di {ev[0].strip()}" for ev in events]) or "   (Riwayat posisi belum terinci)"
                
                status_msg = f"📌 **Status Surat: {nomor_nd}**\n\n"
                status_msg += f"📝 **Hal:** _{hal}_\n"
                status_msg += f"🏢 **Asal:** {from_unit}\n"
                status_msg += f"📜 **Disposisi Intruksi:** {dispo}\n"
                status_msg += f"⏳ **Timeline Posisi:**\n{timeline}\n\n"
                
                # Determine current status based on last event
                if events:
                    last_unit = events[-1][0].strip().upper()
                    status_msg += f"🚀 **Posisi Saat Ini:** {last_unit}\n"
                    if "PUU" in last_unit:
                        status_msg += "✅ **Sedang dalam proses di Kelompok Substansi PUU.**"
                    else:
                        status_msg += f"⚠️ **Surat masih berada di unit {last_unit}, belum masuk ke PUU.**"
                else:
                    status_msg += f"📍 **Posisi:** {raw_posisi or 'Belum terupdate'}"
                
                return [TextContent(type="text", text=status_msg)]
        finally:
            conn.close()

    async def tool_kirim_reminder(self, no_surat: str, pesan: str) -> list[TextContent]:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        admin_id = os.getenv("TELEGRAM_ADMIN_USERS", "").split(",")[0]
        
        if not token or not admin_id:
            return [TextContent(type="text", text="❌ Konfigurasi Telegram belum lengkap di .env server.")]

        conn = self._get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT nomor_nd, hal, posisi FROM korespondensi_raw_pool WHERE nomor_nd ILIKE %s LIMIT 1", (f"%{no_surat}%",))
                row = cur.fetchone()
                if not row: return [TextContent(type="text", text=f"❌ Surat '{no_surat}' tidak ditemukan.")]
                
                full_no = row[0]
                hal = row[1]
                posisi = row[2] or "Unknown"
                
                msg = f"🔔 *REMINDER KOORDINASI SURAT*\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"📂 *No:* `{full_no}`\n"
                msg += f"📝 *Hal:* {hal}\n"
                msg += f"📍 *Posisi:* {posisi}\n"
                msg += f"━━━━━━━━━━━━━━━━━━━━\n"
                msg += f"💬 *Pesan Agent:* {pesan or 'Mohon segera ditindaklanjuti untuk masuk ke koordinasi PUU.'}\n\n"
                msg += f"🌐 _Sent via Universal MCP Server_"
                
                import httpx
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                try:
                    res = httpx.post(url, json={"chat_id": admin_id, "text": msg, "parse_mode": "Markdown"}, timeout=10.0)
                    if res.status_code == 200:
                        return [TextContent(type="text", text=f"✅ Reminder berhasil dikirim ke Admin/Operator PUU untuk surat: {full_no}")]
                    else:
                        return [TextContent(type="text", text=f"❌ Gagal mengirim via Telegram API: {res.text}")]
                except Exception as e:
                    return [TextContent(type="text", text=f"❌ Network Error: {str(e)}")]
        finally:
            conn.close()

    async def run(self):
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream, 
                write_stream, 
                self.server.create_initialization_options()
            )

if __name__ == "__main__":
    mcp_app = KorespondensiMCP()
    asyncio.run(mcp_app.run())
