# RAG知识库配置文件
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent

# 文档目录路径（可通过环境变量 RAG_DOCUMENTS_DIR 覆盖）
DOCUMENTS_DIR = os.environ.get(
    "RAG_DOCUMENTS_DIR",
    str(_PROJECT_ROOT / "data" / "extracted_readmes"),
)

# 向量数据库路径
DB_PATH = "./chroma_db"

# 集合名称
COLLECTION_NAME = "security_knowledge"

# Embedding模型
EMBEDDING_MODEL = "nomic-embed-text"

# 文档分块参数
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# 批处理大小
BATCH_SIZE = 100
