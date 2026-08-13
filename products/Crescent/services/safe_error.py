"""安全错误处理 — CWE-209 防护

对外返回友好消息，对内记录完整异常。
参照 OWASP ASVS 4.0 V7.4.1: 错误消息不暴露敏感信息。
"""
import sys
import traceback


def safe_error(exception, context=""):
    """记录完整异常到 stderr，返回对用户安全的错误消息。
    用法:
        except Exception as e:
            return jsonify(safe_error(e, "agent_chat")), 500
    """
    # 记录完整 traceback 到 stderr（仅供运维/开发者）
    print(f"[ERROR] {context}: {type(exception).__name__}: {exception}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)

    # 对外返回友好消息
    return {"error": "服务器处理请求时出错，请稍后重试"}
