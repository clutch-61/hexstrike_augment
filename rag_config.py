# RAG知识库配置文件

# 文档目录路径
DOCUMENTS_DIR = "/disk1/users/user/UltraRAG/data/extracted_readmes"

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
