import redis
from flask import current_app

_redis_client = None


def get_redis(app=None):
    """获取 Redis 客户端（惰性单例）

    进程内只创建一个连接池；app 参数用于 create_app 阶段（此时无应用上下文），
    运行期调用可省略，自动取 current_app.config。
    """
    global _redis_client
    if _redis_client is None:
        cfg = app.config if app is not None else current_app.config
        _redis_client = redis.Redis(
            host=cfg.get('REDIS_HOST', '127.0.0.1'),
            port=cfg.get('REDIS_PORT', 6379),
            db=cfg.get('REDIS_DB', 0),
            password=cfg.get('REDIS_PASSWORD') or None,
            socket_connect_timeout=3,
            socket_timeout=3,
            # 注意：保持默认 bytes 模式（decode_responses=False）。
            # 1) Flask-Session 的序列化数据是 bytes；
            # 2) 本地 Redis 是 3.0 老版本，redis-py 必须用 4.6.x（纯 RESP2，
            #    新版 redis-py 连接时会发 HELLO 做 RESP3 握手，老服务器不认识）。
        )
    return _redis_client


def check_redis_connection(app=None):
    """启动时探测 Redis 连通性，返回 bool"""
    try:
        return bool(get_redis(app).ping())
    except Exception:
        return False
