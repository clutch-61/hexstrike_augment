"""
RAG检索器模块
整合文档处理和向量搜索功能
"""

from typing import List, Dict, Optional
from .document_processor import DocumentProcessor
from .vector_store import VectorStore


class RAGRetriever:
    """RAG检索器，整合文档处理和向量搜索"""
    
    def __init__(
        self,
        vector_store: VectorStore,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        初始化RAG检索器
        
        Args:
            vector_store: 向量存储实例
            chunk_size: 文档块大小
            chunk_overlap: 文档块重叠大小
        """
        self.vector_store = vector_store
        self.doc_processor = DocumentProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    
    def index_documents(self, documents_directory: str):
        """
        索引文档目录
        
        Args:
            documents_directory: 文档目录路径
        """
        print(f"开始索引文档目录: {documents_directory}")
        
        # 加载文档
        documents = self.doc_processor.load_markdown_files(documents_directory)
        
        # 分块
        chunked_docs = self.doc_processor.chunk_documents(documents)
        
        # 添加到向量数据库
        self.vector_store.add_documents(chunked_docs)
        
        print("文档索引完成！")
    
    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        filter_cve: Optional[str] = None
    ) -> List[Dict]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            filter_cve: CVE ID过滤（可选）
            
        Returns:
            检索结果列表
        """
        # 检测是否主要是CVE ID查询
        import re
        cve_pattern = r'CVE-\d{4}-\d{4,7}'
        cves_in_query = re.findall(cve_pattern, query.upper())
        
        # 如果查询主要是CVE ID，尝试从数据库中找到该文档并提取关键词
        enhanced_query = query
        if cves_in_query and len(query) < 50:
            # 尝试通过文件名直接查找
            target_cve = cves_in_query[0] if len(cves_in_query) == 1 else (filter_cve or cves_in_query[0])
            all_data = self.vector_store.collection.get()
            
            # 查找匹配的文档
            for i, (doc, meta) in enumerate(zip(all_data['documents'], all_data['metadatas'])):
                filename = meta.get('filename', '')
                cve_ids = meta.get('cve_ids', '')
                
                if target_cve in filename or target_cve in cve_ids:
                    # 找到了！从文档内容中提取关键词
                    title = meta.get('title', '')
                    # 提取文档前200字符作为上下文
                    context = doc[:200] if len(doc) > 200 else doc
                    # 移除markdown标记
                    context = re.sub(r'[#*`\[\]()]', ' ', context)
                    # 组合查询
                    enhanced_query = f"{title} {context}"[:500]  # 限制长度
                    break
            
            # 如果没找到，添加通用关键词
            if enhanced_query == query:
                enhanced_query = query + " vulnerability security exploit"
        
        # 搜索
        search_n_results = max(n_results * 20, 100) if filter_cve else n_results
        
        results = self.vector_store.search(
            query=enhanced_query,
            n_results=search_n_results,
            filter_dict=None
        )
        
        # 格式化结果
        formatted_results = []
        
        if results['documents'] and len(results['documents']) > 0:
            for i in range(len(results['documents'][0])):
                metadata = results['metadatas'][0][i]
                
                # 如果指定了CVE过滤，检查是否匹配
                if filter_cve:
                    cve_ids = metadata.get('cve_ids', '')
                    filename = metadata.get('filename', '')
                    
                    # 检查CVE ID是否在cve_ids字段中，或文件名中
                    if filter_cve not in cve_ids and filter_cve not in filename:
                        continue
                
                result = {
                    'content': results['documents'][0][i],
                    'metadata': metadata,
                    'distance': results['distances'][0][i] if 'distances' in results else None
                }
                formatted_results.append(result)
                
                # 如果已经有足够的结果，停止
                if len(formatted_results) >= n_results:
                    break
        
        return formatted_results
    
    def retrieve_with_context(
        self,
        query: str,
        n_results: int = 3
    ) -> str:
        """
        检索相关文档并格式化为上下文字符串
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            
        Returns:
            格式化的上下文字符串
        """
        results = self.retrieve(query, n_results)
        
        if not results:
            return "未找到相关文档。"
        
        context_parts = []
        context_parts.append(f"找到 {len(results)} 个相关文档：\n")
        
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            content = result['content']
            
            context_parts.append(f"\n--- 文档 {i} ---")
            context_parts.append(f"标题: {metadata.get('title', '未知')}")
            context_parts.append(f"来源: {metadata.get('filename', '未知')}")
            
            if 'cve_ids' in metadata:
                context_parts.append(f"CVE: {metadata['cve_ids']}")
            
            if result['distance'] is not None:
                context_parts.append(f"相似度: {1 - result['distance']:.3f}")
            
            context_parts.append(f"\n内容:\n{content}\n")
        
        return "\n".join(context_parts)
    
    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        return self.vector_store.get_collection_stats()
