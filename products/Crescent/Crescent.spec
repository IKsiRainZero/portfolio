# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('templates', 'templates'), ('static', 'static'), ('prompts', 'prompts'), ('data', 'data'), ('image', 'image'), ('../知识库', '知识库'), ('.env.example', '.')],
    hiddenimports=['routes', 'routes.api_agent', 'routes.api_code', 'routes.api_config', 'routes.api_eval', 'routes.api_import', 'routes.api_knowledge', 'routes.api_sync', 'routes.pages', 'services', 'services.agent_service', 'services.rag_service', 'services.knowledge_sync', 'services.knowledge_ingest', 'services.deepseek_client', 'services.llm_fallback', 'services.local_llm', 'services.code_runner', 'services.progress_tracker', 'services.source_tracer', 'services.review_agent', 'services.agent_logger', 'services.rate_limiter', 'services.user_settings', 'services.arxiv_client', 'services.paper_summarizer', 'services.credibility_gate', 'services.srs_scheduler', 'services.eval', 'services.eval.eval_engine', 'services.eval.llm_judge', 'services.eval.trace_logger', 'services.eval.eval_store', 'services.eval.meta_evaluator', 'services.data_sources', 'services.data_sources.news_source', 'sentence_transformers', 'chromadb', 'langchain', 'langchain_core', 'langgraph', 'jieba', 'rank_bm25', 'huggingface_hub', 'PIL', 'fitz', 'markdown', 'bs4', 'uvicorn', 'uvicorn.loops', 'uvicorn.loops.auto', 'starlette', 'fastapi'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Crescent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Crescent',
)
