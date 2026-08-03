"""
port_core.py — 端口占用查询 / 进程结束 核心逻辑

封装 Windows 原生命令：
  - netstat -ano | findstr    查询端口占用（含 PID）
  - tasklist /FO CSV          根据 PID 取进程名
  - taskkill /PID /F [/T]     结束进程

所有对端口 / PID 的入参都会先做整数校验，避免命令注入。
"""

import os
import sys
import re
import csv
import io
import subprocess

# 常用端口收藏持久化文件
# 开发运行(python port_manager.py)：落在脚本同目录
# 打包成 exe 后(sys.frozen)：落在 exe 同目录，保证收藏重启不丢
if getattr(sys, "frozen", False):
    _BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTS_FILE = os.path.join(_BASE_DIR, "ports.json")


def _is_valid_port(port) -> bool:
    try:
        p = int(port)
        return 1 <= p <= 65535
    except (TypeError, ValueError):
        return False


def _local_port_of(addr: str) -> str:
    """从本地地址（0.0.0.0:8080 / [::]:8080 / [fe80::1]:8080）中取出端口号。"""
    if not addr:
        return ""
    # 取最后一个 ':' 之后的部分，规避 IPv6 中 :: 的冒号干扰
    return addr.rsplit(":", 1)[-1]


def get_process_name(pid: int) -> str:
    """根据 PID 查询进程映像名（通过 tasklist）。查询失败返回 '(未知)'。"""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="gbk",
            errors="ignore",
            timeout=10,
        )
        for raw in out.stdout.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            row = next(csv.reader(io.StringIO(raw)))
            if len(row) >= 2 and row[1] == str(pid):
                return row[0]
    except Exception:
        pass
    return "(未知)"


def query_port(port) -> tuple:
    """
    查询端口占用情况。

    返回 (rows, cmd, raw_output)
      rows: dict 列表，字段 proto/local/foreign/state/pid/name
      cmd:  实际执行的命令字符串（netstat ... | findstr ...）
      raw_output: netstat 原始输出（已 decode）
    """
    if not _is_valid_port(port):
        raise ValueError(f"非法端口号: {port!r}（应为 1-65535 的整数）")

    port = int(port)
    # 用 findstr 做初筛，命令与用户心智模型一致；精确匹配交给 Python
    cmd = f'netstat -ano | findstr /R ":{port} "'
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="gbk",
            errors="ignore",
            timeout=20,
        )
        raw = proc.stdout
    except subprocess.TimeoutExpired:
        return [], cmd, "(命令执行超时)"
    except Exception as e:  # noqa: BLE001
        return [], cmd, f"(执行异常: {e})"

    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        # 仅处理以协议开头的行，规避表头等干扰
        if not parts or parts[0] not in ("TCP", "TCPv6", "UDP", "UDPv6"):
            continue
        proto = parts[0]
        local = parts[1] if len(parts) > 1 else ""
        foreign = parts[2] if len(parts) > 2 else ""
        if proto.startswith("TCP"):
            state = parts[3] if len(parts) > 3 else ""
            pid = parts[4] if len(parts) > 4 else parts[-1]
        else:  # UDP 无状态列
            state = ""
            pid = parts[3] if len(parts) > 3 else parts[-1]

        # 精确匹配“本地地址”端口，避免命中外部地址里相同数字
        if _local_port_of(local) != str(port):
            continue
        try:
            pid_int = int(pid)
        except ValueError:
            continue
        rows.append(
            {
                "proto": proto,
                "local": local,
                "foreign": foreign,
                "state": state,
                "pid": pid_int,
                "name": get_process_name(pid_int),
            }
        )

    # 去重（同一 PID 可能同时出现在 TCP/UDP）
    seen = set()
    unique = []
    for r in rows:
        key = (r["proto"], r["pid"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique, cmd, raw


def kill_process(pid, tree: bool = False) -> tuple:
    """
    结束指定 PID 的进程。

    返回 (ok, cmd, output)
      ok:     bool，是否成功
      cmd:    实际执行的命令
      output: 命令输出（含错误信息）
    """
    if not isinstance(pid, int):
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return False, "", f"非法 PID: {pid!r}"

    args = ["taskkill", "/PID", str(pid), "/F"]
    if tree:
        args.append("/T")
    cmd = " ".join(args)

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="gbk",
            errors="ignore",
            timeout=15,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0
        return ok, cmd, output.strip()
    except subprocess.TimeoutExpired:
        return False, cmd, "(taskkill 执行超时)"
    except Exception as e:  # noqa: BLE001
        return False, cmd, f"(执行异常: {e})"


# ---------------- 常用端口收藏持久化 ----------------

def load_favorites() -> list:
    """读取收藏端口列表（去重、升序）。文件不存在或损坏时返回空列表。"""
    try:
        with open(PORTS_FILE, "r", encoding="utf-8") as f:
            data = __import__("json").load(f)
        ports = [int(p) for p in data.get("favorites", []) if _is_valid_port(p)]
    except Exception:
        ports = []
    return sorted(set(ports))


def save_favorites(ports: list) -> None:
    """将端口列表（去重、升序）写回 ports.json。"""
    ports = sorted({int(p) for p in ports if _is_valid_port(p)})
    with open(PORTS_FILE, "w", encoding="utf-8") as f:
        __import__("json").dump({"favorites": ports}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 简单自测
    test_port = 8080
    rows, cmd, raw = query_port(test_port)
    print("CMD:", cmd)
    print("RAW:", raw[:300])
    print(f"找到 {len(rows)} 条占用记录:")
    for r in rows:
        print(f"  {r['proto']:6} {r['local']:22} {r['foreign']:22} {r['state']:12} PID={r['pid']} {r['name']}")
