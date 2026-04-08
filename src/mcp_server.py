import os
import sys
import logging
import asyncio
import re
from typing import Dict, List, Any, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from .database import execute_query

logger = logging.getLogger("mcp_server")

class KorespondensiMCP:
    def __init__(self):
        self.server = Server("korespondensi-server")
        self._setup_tools()

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
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
            try:
                if name == "cari_surat":
                    return await self.tool_cari_surat(arguments["query"], arguments.get("limit", 5))
                elif name == "status_disposisi":
                    return await self.tool_status_disposisi(arguments["no_surat"])
                else:
                    raise ValueError(f"Tool {name} tidak ditemukan.")
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

    async def tool_cari_surat(self, query: str, limit: int) -> list[TextContent]:
        sql = """
            SELECT source_sheet_name as tipe, nomor_nd, hal, dari, posisi, updated_at 
            FROM korespondensi_raw_pool 
            WHERE (nomor_nd ILIKE %s OR hal ILIKE %s OR disposisi ILIKE %s)
            ORDER BY updated_at DESC LIMIT %s
        """
        pattern = f"%{query}%"
        rows = execute_query(sql, (pattern, pattern, pattern, limit))
        
        if not rows:
            return [TextContent(type="text", text=f"🔍 Tidak ditemukan surat dengan query: '{query}'")]
            
        results = []
        for i, r in enumerate(rows, 1):
            hal_trunc = r['hal'][:120] + "..." if len(r['hal']) > 120 else r['hal']
            results.append(f"{i}. [{r['tipe']}] No: {r['nomor_nd']}\n   📝 Hal: {hal_trunc}\n   📍 Posisi: {r['posisi'] or '-'}")
        
        return [TextContent(type="text", text="\n\n".join(results))]

    async def tool_status_disposisi(self, no_surat: str) -> list[TextContent]:
        sql = """
            SELECT nomor_nd, posisi, disposisi, dari, hal 
            FROM korespondensi_raw_pool 
            WHERE nomor_nd ILIKE %s LIMIT 1
        """
        rows = execute_query(sql, (f"%{no_surat}%",))
        if not rows:
            return [TextContent(type="text", text=f"❌ Surat '{no_surat}' tidak ditemukan di database pusat.")]
        
        row = rows[0]
        events = re.findall(r'([A-Z\d\.\s]+)\s+(\d{1,2}/\d{1,2})', row['posisi'] or "")
        timeline = "\n".join([f"   🗓️ {ev[1]} : Di {ev[0].strip()}" for ev in events]) or "   (Riwayat posisi belum terinci)"
        
        status_msg = f"📌 **Status Surat: {row['nomor_nd']}**\n\n"
        status_msg += f"📝 **Hal:** _{row['hal']}_\n"
        status_msg += f"🏢 **Asal:** {row['dari']}\n"
        status_msg += f"📜 **Disposisi Intruksi:** {row['disposisi'] or '-'}\n"
        status_msg += f"⏳ **Timeline Posisi:**\n{timeline}\n\n"
        
        if events:
            last_unit = events[-1][0].strip().upper()
            status_msg += f"🚀 **Posisi Saat Ini:** {last_unit}\n"
            if "PUU" in last_unit:
                status_msg += "✅ **Sedang dalam proses di Kelompok Substansi PUU.**"
            else:
                status_msg += f"⚠️ **Surat masih berada di unit {last_unit}, belum masuk ke PUU.**"
        else:
            status_msg += f"📍 **Posisi:** {row['posisi'] or 'Belum terupdate'}"
            
        return [TextContent(type="text", text=status_msg)]

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
