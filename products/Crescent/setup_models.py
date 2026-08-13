"""Portfolio App 首次运行初始化 — 下载模型 + 构建向量库

用法:
  python setup_models.py              # 标准初始化
  python setup_models.py --no-vecdb   # 只下载模型，不构建向量库
  python setup_models.py --no-models  # 只构建向量库，不下载模型
"""
import sys
import os
from pathlib import Path

# 确保项目目录在 sys.path
sys.path.insert(0, str(Path(__file__).parent))


def download_models():
    """下载 bge-m3 embedding 模型到 models/ 目录"""
    models_dir = Path(os.environ.get("MODELS_DIR", Path(__file__).parent / "models"))
    bge_m3_path = models_dir / "BAAI" / "bge-m3"

    if bge_m3_path.exists():
        print(f"[ok] bge-m3 模型已存在: {bge_m3_path}")
        return True

    print("下载 bge-m3 embedding 模型 (~2GB)...")
    print(f"目标路径: {bge_m3_path}")
    print()

    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            "BAAI/bge-m3",
            local_dir=str(bge_m3_path),
            local_dir_use_symlinks=False,
        )
        print(f"[ok] 模型下载完成: {bge_m3_path}")
        return True
    except Exception as e:
        print(f"[!!] 自动下载失败: {e}")
        print()
        print("手动下载方式:")
        print(f"  1. 访问 https://huggingface.co/BAAI/bge-m3")
        print(f"  2. 下载所有文件到: {bge_m3_path}")
        print(f"  3. 或使用 modelscope: git clone https://www.modelscope.cn/BAAI/bge-m3.git \"{bge_m3_path}\"")
        return False


def build_vecdb():
    """从 data/knowledge/*.json 构建 ChromaDB 向量库"""
    print("构建 ChromaDB 向量库...")
    try:
        from services.knowledge_sync import sync_knowledge_to_chroma
        result = sync_knowledge_to_chroma()
        print(f"[ok] 向量库构建完成: 新增 {result['added']} chunks, "
              f"总计 {result['total_chunks']} chunks")
        return True
    except Exception as e:
        print(f"[!!] 构建失败: {e}")
        return False


def check_env():
    """检查必要配置"""
    issues = []

    # Python 版本
    if sys.version_info < (3, 10):
        issues.append("需要 Python 3.10+")

    # API Key
    if not os.environ.get("DEEPSEEK_API_KEY"):
        key_file = Path(__file__).parent / ".env"
        if key_file.exists():
            # 尝试从 .env 读取
            with open(key_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        val = line.split("=", 1)[1].strip()
                        if val and val != "sk-your-key-here":
                            os.environ["DEEPSEEK_API_KEY"] = val
                            break
        if not os.environ.get("DEEPSEEK_API_KEY"):
            issues.append("DEEPSEEK_API_KEY 未设置 — AI 功能将不可用。"
                          "复制 .env.example 为 .env 并填写你的 API Key")

    for issue in issues:
        print(f"[!!] {issue}")

    return len(issues) == 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Portfolio App 首次初始化")
    parser.add_argument("--no-vecdb", action="store_true", help="跳过向量库构建")
    parser.add_argument("--no-models", action="store_true", help="跳过模型下载")
    args = parser.parse_args()

    print("=" * 50)
    print("  Portfolio App — 首次运行初始化")
    print("=" * 50)
    print()

    # 1. 检查环境
    print("[1/3] 检查环境配置...")
    check_env()
    print()

    # 2. 下载模型
    print("[2/3] Embedding 模型...")
    if not args.no_models:
        download_models()
    else:
        print("(已跳过 --no-models)")
    print()

    # 3. 构建向量库
    print("[3/3] 向量库...")
    if not args.no_vecdb:
        build_vecdb()
    else:
        print("(已跳过 --no-vecdb)")
    print()

    print("=" * 50)
    print("  初始化完成！")
    print(f"  启动: python server.py")
    print(f"  访问: http://localhost:5000")
    print("=" * 50)


if __name__ == "__main__":
    main()
