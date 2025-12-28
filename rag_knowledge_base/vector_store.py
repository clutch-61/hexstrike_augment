"""
向量存储模块
使用ChromaDB存储和检索文档向量
"""

import os
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
import ollama


class VectorStore:
    """向量数据库管理类"""
    
    def __init__(
        self, 
        persist_directory: str = "./chroma_db",
        collection_name: str = "security_knowledge",
        embedding_model: str = "nomic-embed-text"
    ):
        """
        初始化向量存储
        
        Args:
            persist_directory: 数据库持久化目录
            collection_name: 集合名称
            embedding_model: Ollama embedding模型名称
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        print(f"向量数据库初始化完成: {persist_directory}")
        print(f"集合: {collection_name}, 文档数: {self.collection.count()}")
    
    def get_embedding(self, text: str) -> List[float]:
        """
        使用Ollama生成文本嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量
        """
        try:
            response = ollama.embeddings(
                model=self.embedding_model,
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            print(f"生成嵌入向量失败: {e}")
            # 如果模型不存在，尝试拉取
            print(f"尝试拉取模型: {self.embedding_model}")
            try:
                ollama.pull(self.embedding_model)
                response = ollama.embeddings(
                    model=self.embedding_model,
                    prompt=text
                )
                return response['embedding']
            except Exception as e2:
                raise Exception(f"无法使用embedding模型 {self.embedding_model}: {e2}")
    
    def add_documents(
        self, 
        documents: List[Dict[str, str]], 
        batch_size: int = 100
    ):
        """
        添加文档到向量数据库
        
        Args:
            documents: 文档列表，每个文档包含content和metadata
            batch_size: 批处理大小
        """
        total = len(documents)
        print(f"开始添加 {total} 个文档到向量数据库...")
        
        for i in range(0, total, batch_size):
            batch = documents[i:i + batch_size]
            
            # 准备数据
            ids = []
            embeddings = []
            metadatas = []
            documents_text = []
            
            for j, doc in enumerate(batch):
                # 生成唯一ID
                doc_id = doc['metadata'].get('doc_id', str(i + j))
                chunk_id = doc['metadata'].get('chunk_id', 0)
                unique_id = f"{doc_id}_{chunk_id}"
                
                ids.append(unique_id)
                documents_text.append(doc['content'])
                
                # 生成嵌入向量
                embedding = self.get_embedding(doc['content'])
                embeddings.append(embedding)
                
                # 准备元数据（ChromaDB只支持基本类型）
                metadata = {
                    'source': doc['metadata'].get('source', ''),
                    'filename': doc['metadata'].get('filename', ''),
                    'title': doc['metadata'].get('title', ''),
                    'chunk_id': str(chunk_id)
                }
                
                # 添加可选字段
                if 'cve_ids' in doc['metadata']:
                    metadata['cve_ids'] = doc['metadata']['cve_ids']
                if 'origin' in doc['metadata']:
                    metadata['origin'] = doc['metadata']['origin']
                if 'date' in doc['metadata']:
                    metadata['date'] = doc['metadata']['date']
                
                metadatas.append(metadata)
            
            # 添加到集合
            try:
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents_text,
                    metadatas=metadatas
                )
                print(f"已添加 {i + len(batch)}/{total} 个文档")
            except Exception as e:
                print(f"添加文档批次失败 {i}-{i+len(batch)}: {e}")
        
        print(f"完成！向量数据库现有 {self.collection.count()} 个文档")
    
    def search(
        self, 
        query: str, 
        n_results: int = 5,
        filter_dict: Optional[Dict] = None
    ) -> Dict:
        """
        搜索相似文档
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            filter_dict: 元数据过滤条件
            
        Returns:
            搜索结果
        """
        # 生成查询向量
        query_embedding = self.get_embedding(query)
        
        # 搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_dict if filter_dict else None
        )
        
        return results
    
    def delete_all(self):
        """删除集合中的所有文档"""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        print("已清空向量数据库")
    
    def get_collection_stats(self) -> Dict:
        """获取集合统计信息"""
        count = self.collection.count()
        return {
            'collection_name': self.collection_name,
            'document_count': count,
            'persist_directory': self.persist_directory
        }
