"""Crescent 启动器 — 自动检测模型 → 下载(如缺失) → 启动服务器 → 打开浏览器"""
import sys
import os
import time
import threading
import webbrowser
import traceback
from pathlib import Path


# 轻量诊断追踪 (仅在 PyInstaller 管道模式或崩溃时有用)
TRACE_FILE = Path(os.environ.get("TEMP", "")) / "crescent_trace.log" if os.environ.get("TEMP") else None


def _trace(msg):
    if TRACE_FILE:
        try:
            with open(TRACE_FILE, "a", encoding="utf-8") as f:
                f.write(f"{msg}\n")
                f.flush()
        except Exception:
            pass


def _trace_exc():
    if TRACE_FILE:
        try:
            with open(TRACE_FILE, "a", encoding="utf-8") as f:
                traceback.print_exc(file=f)
                f.flush()
        except Exception:
            pass


def get_base_dir():
    """获取数据文件所在目录 (兼容 PyInstaller onedir/onefile 和直接运行)"""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        return Path(__file__).parent  # onedir: 数据在 _internal/
    return Path(__file__).parent


BASE_DIR = get_base_dir()
MODELS_DIR = BASE_DIR / "models"


def check_models():
    """检查 embedding 模型是否存在，返回 (bge_ok, reranker_ok)"""
    bge_path = MODELS_DIR / "BAAI" / "bge-m3"
    reranker_path = MODELS_DIR / "BAAI" / "bge-reranker-large"
    return bge_path.exists(), reranker_path.exists()


def download_models():
    """下载缺失的模型"""
    bge_path = MODELS_DIR / "BAAI" / "bge-m3"
    if not bge_path.exists():
        print("[Crescent] 下载 BAAI/bge-m3 embedding 模型 (~2GB)...", flush=True)
        print(f"[Crescent] 目标: {bge_path}", flush=True)
        try:
            from huggingface_hub import snapshot_download
            snapshot_download("BAAI/bge-m3", local_dir=str(bge_path),
                              local_dir_use_symlinks=False)
            print("[Crescent] bge-m3 下载完成", flush=True)
        except Exception as e:
            print(f"[Crescent] 下载失败: {e}", flush=True)
            print(f"[Crescent] 请手动下载到: {bge_path}", flush=True)
            return False
    else:
        print("[Crescent] bge-m3 已存在, 跳过下载", flush=True)

    reranker_path = MODELS_DIR / "BAAI" / "bge-reranker-large"
    if not reranker_path.exists():
        print("[Crescent] 下载 BAAI/bge-reranker-large (~1.3GB)...", flush=True)
        try:
            from huggingface_hub import snapshot_download
            snapshot_download("BAAI/bge-reranker-large",
                              local_dir=str(reranker_path),
                              local_dir_use_symlinks=False)
            print("[Crescent] Reranker 下载完成", flush=True)
        except Exception as e:
            print(f"[Crescent] Reranker 下载失败 (非致命): {e}", flush=True)
    else:
        print("[Crescent] Reranker 已存在, 跳过下载", flush=True)

    return True


def check_vecdb():
    """检查 ChromaDB 向量库是否存在"""
    return (BASE_DIR / "data" / "chroma_db").exists()


def build_vecdb():
    """构建向量库"""
    print("[Crescent] 构建 ChromaDB 向量库...", flush=True)
    try:
        from services.knowledge_sync import sync_knowledge_to_chroma
        result = sync_knowledge_to_chroma()
        print(f"[Crescent] 向量库完成: {result['total_chunks']} chunks", flush=True)
        return True
    except Exception as e:
        print(f"[Crescent] 向量库构建失败: {e}", flush=True)
        return False


def main():
    os.chdir(str(BASE_DIR))
    sys.path.insert(0, str(BASE_DIR))

    print("=" * 50, flush=True)
    print("  Crescent — AI 终生学习伙伴", flush=True)
    print("=" * 50, flush=True)

    # 1. 检查 + 下载模型
    bge_ok, reranker_ok = check_models()
    if not bge_ok:
        print()
        print("[Crescent] 首次运行 — 需要下载 embedding 模型 (~2GB)", flush=True)
        print("[Crescent] 请确保网络连接正常，下载约需 3-5 分钟", flush=True)
        print()
        if not download_models():
            print()
            print("[Crescent] 模型下载失败，请检查网络后重试", flush=True)
            print("[Crescent] 按回车退出...", flush=True)
            input()
            sys.exit(1)

    # 2. 检查 + 构建向量库
    if not check_vecdb():
        print()
        if not build_vecdb():
            print("[Crescent] 向量库构建失败，将跳过 (RAG 功能不可用)", flush=True)

    # 3. 检查 API Key
    if not os.environ.get("DEEPSEEK_API_KEY"):
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        val = line.split("=", 1)[1].strip()
                        if val and val != "sk-your-key-here":
                            os.environ["DEEPSEEK_API_KEY"] = val
                            break
        if not os.environ.get("DEEPSEEK_API_KEY"):
            print("[Crescent] 未检测到 API Key，AI 功能不可用", flush=True)
            print("[Crescent] 启动后访问 http://localhost:5000/settings 配置", flush=True)

    # 4. 启动服务器 (在 daemon 线程)
    import uvicorn
    import main  # 显式导入让 PyInstaller 追踪依赖

    def run_server():
        uvicorn.run(main.app, host="127.0.0.1", port=5000, log_level="info")

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # 5. 等待服务器就绪 + 打开浏览器
    print("[Crescent] 启动中...", flush=True)
    time.sleep(2)

    import urllib.request
    for i in range(15):
        try:
            urllib.request.urlopen("http://127.0.0.1:5000", timeout=1)
            break
        except Exception:
            time.sleep(1)
    else:
        print("[Crescent] 服务器启动较慢，请手动访问 http://localhost:5000", flush=True)

    webbrowser.open("http://localhost:5000")
    print("[Crescent] 浏览器已打开 — http://localhost:5000", flush=True)
    print("[Crescent] 关闭此窗口将停止服务", flush=True)

    # 6. 保持运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[Crescent] 已停止", flush=True)


if __name__ == "__main__":
    try:
        _trace("Crescent launcher starting")
        main()
    except Exception:
        _trace("=== LAUNCHER CRASH ===")
        _trace_exc()
        print("FATAL ERROR - 请查看 %TEMP%/crescent_trace.log", flush=True)
        try:
            input("Press Enter to exit...")
        except Exception:
            pass
        sys.exit(1)
