"""
头像获取插件

功能:
- 获取 @用户 或指定 QQ 号的头像，以图片形式发送

命令格式:
- /avatar @用户名  - 获取被 @用户 的头像
- /avatar QQ号    - 获取指定 QQ 号的头像
- 获取头像 @用户名  - 同上
- 获取头像 QQ号    - 同上
"""

import base64
import logging
import re

import aiohttp
from maibot_sdk import Command, Field, MaiBotPlugin, PluginConfigBase

logger = logging.getLogger("avatar_fetcher_plugin")

AVATAR_URL = "https://q1.qlogo.cn/g?b=qq&nk={qq}&s=640"
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=15)


class PluginSectionConfig(PluginConfigBase):
    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0

    enabled: bool = Field(default=False, description="是否启用插件")
    config_version: str = Field(default="1.0.0", description="配置版本")


class AvatarFetcherPluginConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)


class AvatarFetcherPlugin(MaiBotPlugin):

    config_model = AvatarFetcherPluginConfig

    async def on_load(self) -> None:
        pass

    async def on_unload(self) -> None:
        pass

    async def on_config_update(self, scope: str, config_data: dict[str, object], version: str) -> None:
        pass

    @Command("avatar", description="获取 @用户 或指定 QQ 号的头像", pattern=r"^(?:/avatar|获取头像)\s*(.*)$")
    async def handle_avatar(self, stream_id: str = "", text: str = "", **kwargs):
        try:
            if not self.config.plugin.enabled:
                await self.ctx.send.text("头像获取插件未启用", stream_id)
                return False, "插件未启用", True

            target_qq = None

            raw_message = kwargs.get("message")
            if isinstance(raw_message, dict):
                segments = raw_message.get("raw_message") or []
                if isinstance(segments, list):
                    for seg in segments:
                        if isinstance(seg, dict) and seg.get("type") == "at":
                            data = seg.get("data", {})
                            if isinstance(data, dict):
                                qq = str(data.get("target_user_id", "")).strip()
                                if qq and qq.isdigit():
                                    target_qq = qq
                                    break

            if not target_qq:
                match = re.match(r"^(?:/avatar|获取头像)\s*(.*)$", text)
                if match:
                    args = match.group(1).strip()
                    target_qq = self._extract_qq_from_args(args)

            if not target_qq:
                message_dump = repr(raw_message) if raw_message else "N/A"
                logger.debug("FAIL text=%r raw_message=%s", text, message_dump)
                await self.ctx.send.text("请 @一个用户 或输入有效的 QQ 号", stream_id)
                return False, "无效参数", True

            logger.debug("OK target_qq=%s", target_qq)

            await self.ctx.send.text("正在获取头像，请稍候...", stream_id)

            avatar_data = await self._download_avatar(target_qq)
            if avatar_data is None:
                await self.ctx.send.text(f"获取 QQ({target_qq}) 头像失败，请检查 QQ 号是否正确或稍后再试", stream_id)
                return False, "头像下载失败", True

            img_base64 = base64.b64encode(avatar_data).decode("utf-8")
            await self.ctx.send.image(img_base64, stream_id)

            return True, f"已发送 QQ({target_qq}) 头像", True

        except Exception as e:
            logger.exception("执行命令时出错")
            try:
                await self.ctx.send.text(f"获取头像时出错了: {e}", stream_id)
            except Exception:
                pass
            return False, "执行命令时出错", False

    @staticmethod
    async def _download_avatar(qq_id: str) -> bytes | None:
        if not qq_id or not qq_id.isdigit():
            return None

        url = AVATAR_URL.format(qq=qq_id)
        try:
            async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    logger.debug("下载头像失败 (QQ:%s): HTTP %s", qq_id, resp.status)
        except Exception as e:
            logger.debug("下载头像异常 (QQ:%s): %s", qq_id, e)

        return None

    @staticmethod
    def _extract_qq_from_args(args: str) -> str | None:
        """从参数中提取 QQ 号，支持多种格式"""
        # 1. [CQ:at,qq=123456] 或 [CQ:at,qq=123456,name=xxx] 等
        at_match = re.search(r'\[CQ:at,qq=(\d+)', args)
        if at_match:
            return at_match.group(1)

        # 2. @123456 (用户手动输入数字)
        at_digit_match = re.search(r'@(\d+)', args)
        if at_digit_match:
            return at_digit_match.group(1)

        # 3. 纯数字
        if args.isdigit():
            return args

        return None


def create_plugin() -> AvatarFetcherPlugin:
    return AvatarFetcherPlugin()
