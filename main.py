from __future__ import annotations

import asyncio
import random
import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

# ==== 可调参数 ====
IGNORE_PROB = 0.05      # 装死概率（5%）
DELAY_MIN = 1.5         # 回复前最小延迟（秒）
DELAY_MAX = 6.0         # 回复前最大延迟（秒）
SOFT_LIMIT = 120        # 超过这个字数才考虑收尾，不是硬截断
SEND_GAP_MIN = 0.8      # 发送前的额外间隔
SEND_GAP_MAX = 2.0
# =================

_SENT_END = re.compile(r"[。！？!?…~～]")


def _soft_trim(text: str) -> str:
    """只在超长时按句末标点收尾，绝不拦腰截断。"""
    if len(text) <= SOFT_LIMIT:
        return text
    head = text[:SOFT_LIMIT]
    cut = None
    for m in _SENT_END.finditer(head):
        cut = m.end()
    if cut and cut >= SOFT_LIMIT // 2:
        return head[:cut]
    # 找不到句末标点就整条放行，宁可长一点也不切
    return text


@register("pacer", "dsh", "节奏控制：随机延迟 + 装死5% + 软收尾", "0.2.0")
class ChatPacer(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def pace_incoming(self, event: AstrMessageEvent):
        """收到消息后：按概率装死，否则随机等一会儿再处理。"""
        try:
            text = (event.get_message_str() or "").strip()
        except Exception:  # noqa: BLE001
            text = ""
        if text.startswith("/") or text.startswith("#"):
            return
        if not text:
            return
        if random.random() < IGNORE_PROB:
            logger.info("[chat_pacer] 装死，跳过这条")
            event.stop_event()
            return
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        logger.info(f"[chat_pacer] 延迟 {delay:.1f}s 后回复")
        await asyncio.sleep(delay)

    @filter.on_decorating_result()
    async def pace_outgoing(self, event: AstrMessageEvent):
        """发送前：随机等一下，必要时按句末收尾（不做硬截断）。"""
        try:
            await asyncio.sleep(random.uniform(SEND_GAP_MIN, SEND_GAP_MAX))
        except Exception:  # noqa: BLE001
            pass
        try:
            result = event.get_result()
            chain = getattr(result, "chain", None) or []
            for comp in chain:
                text = getattr(comp, "text", None)
                if isinstance(text, str) and text:
                    comp.text = _soft_trim(text)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[chat_pacer] 收尾处理失败（忽略）: {exc}")
