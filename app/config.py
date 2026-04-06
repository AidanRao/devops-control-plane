from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    """最小配置对象，从 .env/环境变量中读取关键参数。

    TODO:
    - 后续可切换到 pydantic 的 Settings 管理，支持更多配置项与校验。
    """

    PORT: int = int(os.getenv("PORT", "8000"))
    STATIC_GATEWAY_TOKEN: str = os.getenv("STATIC_GATEWAY_TOKEN", "change_me")
    TICK_INTERVAL_MS: int = int(os.getenv("TICK_INTERVAL_MS", "15000"))

    # 设备令牌有效期（分钟），用于内存中的 deviceToken 过期控制。
    DEVICE_TOKEN_TTL_MINUTES: int = int(os.getenv("DEVICE_TOKEN_TTL_MINUTES", "1440"))

    # 允许的签名时间偏移窗口（秒），防止重放与时钟漂移导致的误判。
    MAX_SKEW_SECONDS: int = int(os.getenv("MAX_SKEW_SECONDS", "300"))


settings = Settings()
