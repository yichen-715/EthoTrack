"""
EthoTrack Pro — 模块授权许可管理器

架构说明：
  1. 激活码格式：  {PREFIX}-{FP6}-{HMAC8}
     - PREFIX : 模块简码 (OF/YM/EP/FS/NR)
     - FP6    : 机器指纹前6位（作为可见检验）
     - HMAC8  : HMAC-SHA256(SECRET, prefix+fp_full) 前8位

  2. 机器指纹：基于 MAC 地址 + 主机名，SHA256 取前12字符
     → 只要硬件不变，指纹永远相同（重装系统/更新软件不影响）

  3. 许可文件：存放在 %APPDATA%\\EthoTrack\\licenses.dat
     → 软件目录之外，更新/重装软件不会清除
     → 文件内容经过简单 XOR 混淆（防止直接查看/篡改）

  4. 重装恢复：因为激活码本身编码了机器ID，同一台机器
     重新输入之前的激活码即可立刻通过验证，无需联网
"""

import hashlib
import hmac
import json
import os
import platform
import uuid
from datetime import datetime
from typing import Dict, Optional

from core.logger import logger


# ─────────────────────────────────────────────
#   开发者密钥（勿泄露，内嵌在软件中）
#   生产中建议替换为一个随机的 32 字节字符串
# ─────────────────────────────────────────────
_SECRET = b"EthoTrack-Pr0-Lic3nse-K3y-2026!"

# ─────────────────────────────────────────────
#   模块注册表
# ─────────────────────────────────────────────
MODULE_REGISTRY: Dict[str, str] = {
    "open_field":     "OF",   # 旷场实验
    "y_maze":         "YM",   # Y迷宫
    "elevated_plus":  "EP",   # 高架十字迷宫
    "forced_swim":    "FS",   # 强迫游泳
    "nor":            "NR",   # 新物体识别
}

# 反向查找：前缀 → module_key
_PREFIX_TO_MODULE = {v: k for k, v in MODULE_REGISTRY.items()}

# 许可文件路径
_LICENSE_DIR  = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "EthoTrack")
_LICENSE_FILE = os.path.join(_LICENSE_DIR, "licenses.dat")

# XOR 混淆密钥（简单防直接查看）
_XOR_KEY = b"EthoXOR#2024"


# ─────────────────────────────────────────────
#   机器指纹
# ─────────────────────────────────────────────
def get_machine_fingerprint() -> str:
    """
    生成本机唯一硬件指纹（12字符，大写十六进制）。
    使用 MAC 地址 + 主机名组合，重装系统后保持不变。
    格式：AAAA-BBBB-CCCC
    """
    try:
        mac = str(uuid.getnode())      # MAC 地址整数
        hostname = platform.node()     # 主机名
        raw = f"{mac}|{hostname}"
        digest = hashlib.sha256(raw.encode()).hexdigest().upper()[:12]
        return f"{digest[:4]}-{digest[4:8]}-{digest[8:12]}"
    except Exception as e:
        logger.warning(f"[License] 获取机器指纹失败: {e}")
        return "UNKN-0000-0000"


def _fp_raw() -> str:
    """返回无分隔符的机器指纹（用于HMAC计算）"""
    return get_machine_fingerprint().replace("-", "")


# ─────────────────────────────────────────────
#   激活码生成与验证
# ─────────────────────────────────────────────
def generate_key(module_key: str, fingerprint_raw: str) -> Optional[str]:
    """
    【开发者工具调用】根据模块和机器指纹生成激活码。

    Args:
        module_key:       模块内部 key，如 "open_field"
        fingerprint_raw:  用户提供的完整12位指纹（无分隔符）

    Returns:
        激活码字符串，如 "OF-A3F7B2-C1D9E4AB"，失败返回 None
    """
    prefix = MODULE_REGISTRY.get(module_key)
    if not prefix:
        return None

    fp6 = fingerprint_raw[:6].upper()
    payload = f"{prefix}:{fingerprint_raw.upper()}"
    sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest().upper()[:8]
    return f"{prefix}-{fp6}-{sig}"


def verify_key(key: str) -> Optional[str]:
    """
    验证激活码是否对当前机器有效。

    Args:
        key: 用户输入的激活码，格式 "OF-A3F7B2-C1D9E4AB"

    Returns:
        模块内部 key（如 "open_field"），验证失败返回 None
    """
    try:
        key = key.strip().upper()
        parts = key.split("-")
        if len(parts) != 3:
            return None

        prefix, fp6, sig_input = parts[0], parts[1], parts[2]
        module_key = _PREFIX_TO_MODULE.get(prefix)
        if not module_key:
            return None

        # 检查指纹前6位是否与本机匹配
        local_fp = _fp_raw().upper()
        if local_fp[:6] != fp6:
            logger.warning("[License] 机器码不匹配")
            return None

        # 重新计算 HMAC 并比对
        payload = f"{prefix}:{local_fp}"
        expected_sig = hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest().upper()[:8]
        if not hmac.compare_digest(sig_input, expected_sig):
            logger.warning("[License] HMAC 校验失败")
            return None

        return module_key

    except Exception as e:
        logger.error(f"[License] 验证异常: {e}")
        return None


# ─────────────────────────────────────────────
#   许可文件读写（XOR 混淆）
# ─────────────────────────────────────────────
def _xor(data: bytes) -> bytes:
    key = _XOR_KEY
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _read_license_file() -> dict:
    try:
        if not os.path.exists(_LICENSE_FILE):
            return {}
        with open(_LICENSE_FILE, "rb") as f:
            raw = _xor(f.read())
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        logger.warning(f"[License] 读取许可文件失败: {e}")
        return {}


def _write_license_file(data: dict):
    try:
        os.makedirs(_LICENSE_DIR, exist_ok=True)
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        with open(_LICENSE_FILE, "wb") as f:
            f.write(_xor(raw))
    except Exception as e:
        logger.error(f"[License] 写入许可文件失败: {e}")


# ─────────────────────────────────────────────
#   LicenseManager — 主入口类
# ─────────────────────────────────────────────
class LicenseManager:
    """
    全局许可管理器（单例使用）。
    在程序启动时实例化一次，之后通过 is_activated() 查询。
    """

    def __init__(self):
        self._data: dict = _read_license_file()

    def reload(self):
        """重新从磁盘加载（激活成功后调用）"""
        self._data = _read_license_file()

    def is_activated(self, module_key: str) -> bool:
        """查询某模块是否已激活"""
        activated = self._data.get("activated", {})
        return module_key in activated

    def get_all_status(self) -> Dict[str, bool]:
        """返回所有模块的激活状态 {module_key: bool}"""
        activated = self._data.get("activated", {})
        return {k: (k in activated) for k in MODULE_REGISTRY}

    def activate(self, key: str) -> tuple:
        """
        尝试激活。

        Returns:
            (True, module_key, module_display_name) — 成功
            (False, error_message, None)             — 失败
        """
        module_key = verify_key(key)
        if not module_key:
            return False, "激活码无效或不适用于本机，请检查后重试", None

        # 写入许可文件
        activated = self._data.get("activated", {})
        activated[module_key] = {
            "key":          key.strip().upper(),
            "activated_at": datetime.now().isoformat(),
            "fingerprint":  get_machine_fingerprint(),
        }
        self._data["activated"] = activated
        _write_license_file(self._data)
        self.reload()

        display_names = {
            "open_field":    "旷场实验",
            "y_maze":        "Y迷宫",
            "elevated_plus": "高架十字迷宫",
            "forced_swim":   "强迫游泳",
            "nor":           "新物体识别",
        }
        return True, None, display_names.get(module_key, module_key)

    def deactivate(self, module_key: str):
        """撤销某模块的激活（管理员操作）"""
        activated = self._data.get("activated", {})
        activated.pop(module_key, None)
        self._data["activated"] = activated
        _write_license_file(self._data)
        self.reload()


# 全局单例实例（在 main.py 中初始化后各模块共用）
license_manager = LicenseManager()
