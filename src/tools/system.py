"""
System information tool.
Get system information, processes, and network status.
"""

import asyncio
import platform
import os
from typing import Any, Dict, Optional
from datetime import datetime

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from .base import BaseTool


class SystemTool(BaseTool):
    """
    Get system information and manage processes.
    """
    
    name = "system"
    description = "System information and process management"
    actions = ["info", "processes", "network", "disk", "memory"]
    capabilities_required = ["system_info"]
    
    async def execute(self, action: str, args: Dict[str, Any]) -> str:
        """Execute a system action."""
        handlers = {
            'info': self._system_info,
            'processes': self._list_processes,
            'network': self._network_info,
            'disk': self._disk_info,
            'memory': self._memory_info,
        }
        
        handler = handlers.get(action, self._system_info)
        return await handler(args)
    
    async def _system_info(self, args: Dict) -> str:
        """Get comprehensive system information."""
        info_lines = ["🖥️ **System Information**\n"]
        
        # Basic system info
        info_lines.extend([
            f"**Platform:** {platform.system()} {platform.release()}",
            f"**Machine:** {platform.machine()}",
            f"**Processor:** {platform.processor()}",
            f"**Python:** {platform.python_version()}",
            f"**Hostname:** {platform.node()}",
        ])
        
        if PSUTIL_AVAILABLE:
            # CPU info
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            info_lines.append(f"\n**CPU:** {cpu_count} cores @ {cpu_percent}% usage")
            
            # Memory info
            memory = psutil.virtual_memory()
            info_lines.append(
                f"**Memory:** {self._format_bytes(memory.used)} / "
                f"{self._format_bytes(memory.total)} ({memory.percent}%)"
            )
            
            # Disk info
            disk = psutil.disk_usage('/')
            info_lines.append(
                f"**Disk:** {self._format_bytes(disk.used)} / "
                f"{self._format_bytes(disk.total)} ({disk.percent}%)"
            )
            
            # Uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            info_lines.append(f"**Uptime:** {str(uptime).split('.')[0]}")
        else:
            info_lines.append("\n⚠️ Install `psutil` for detailed system info")
        
        return "\n".join(info_lines)
    
    async def _list_processes(self, args: Dict) -> str:
        """List running processes."""
        if not PSUTIL_AVAILABLE:
            return "❌ `psutil` not installed. Run: `pip install psutil`"
        
        try:
            limit = args.get('limit', 20)
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'][:30],
                        'cpu': info.get('cpu_percent', 0) or 0,
                        'memory': info.get('memory_percent', 0) or 0,
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by CPU usage
            processes.sort(key=lambda x: x['cpu'], reverse=True)
            processes = processes[:limit]
            
            lines = ["📊 **Top Processes:**\n"]
            lines.append("```")
            lines.append(f"{'PID':<8} {'Name':<30} {'CPU%':<8} {'Mem%':<8}")
            lines.append("-" * 56)
            
            for proc in processes:
                lines.append(
                    f"{proc['pid']:<8} {proc['name']:<30} "
                    f"{proc['cpu']:<8.1f} {proc['memory']:<8.1f}"
                )
            
            lines.append("```")
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error listing processes: {str(e)}"
    
    async def _network_info(self, args: Dict) -> str:
        """Get network information."""
        if not PSUTIL_AVAILABLE:
            return "❌ `psutil` not installed. Run: `pip install psutil`"
        
        try:
            lines = ["🌐 **Network Information**\n"]
            
            # Network interfaces
            interfaces = psutil.net_if_addrs()
            for iface, addrs in interfaces.items():
                for addr in addrs:
                    if addr.family.name == 'AF_INET':  # IPv4
                        lines.append(f"• **{iface}:** {addr.address}")
                        break
            
            # Network I/O
            net_io = psutil.net_io_counters()
            lines.append(f"\n**Network I/O:**")
            lines.append(f"• Sent: {self._format_bytes(net_io.bytes_sent)}")
            lines.append(f"• Received: {self._format_bytes(net_io.bytes_recv)}")
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error getting network info: {str(e)}"
    
    async def _disk_info(self, args: Dict) -> str:
        """Get disk usage information."""
        if not PSUTIL_AVAILABLE:
            return "❌ `psutil` not installed. Run: `pip install psutil`"
        
        try:
            lines = ["💾 **Disk Usage**\n"]
            
            partitions = psutil.disk_partitions()
            for partition in partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    lines.append(
                        f"• **{partition.device}** ({partition.mountpoint}): "
                        f"{self._format_bytes(usage.used)} / {self._format_bytes(usage.total)} "
                        f"({usage.percent}%)"
                    )
                except (PermissionError, OSError):
                    continue
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error getting disk info: {str(e)}"
    
    async def _memory_info(self, args: Dict) -> str:
        """Get detailed memory information."""
        if not PSUTIL_AVAILABLE:
            return "❌ `psutil` not installed. Run: `pip install psutil`"
        
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            lines = [
                "🧠 **Memory Usage**\n",
                "**Physical Memory:**",
                f"• Total: {self._format_bytes(memory.total)}",
                f"• Used: {self._format_bytes(memory.used)} ({memory.percent}%)",
                f"• Available: {self._format_bytes(memory.available)}",
                f"\n**Swap Memory:**",
                f"• Total: {self._format_bytes(swap.total)}",
                f"• Used: {self._format_bytes(swap.used)} ({swap.percent}%)",
            ]
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"❌ Error getting memory info: {str(e)}"
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} PB"
