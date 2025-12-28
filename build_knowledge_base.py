#!/usr/bin/env python3
"""
构建RAG知识库脚本
用于索引markdown文档并构建向量数据库
"""

import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_knowledge_base.vector_store import VectorStore
from rag_knowledge_base.rag_retriever import RAGRetriever


def build_knowledge_base(
    documents_dir: str,
    db_path: str = "./chroma_db",
    rebuild: bool = False
):
    """
    构建RAG知识库
    
    Args:
        documents_dir: markdown文档目录
        db_path: 向量数据库路径
        rebuild: 是否重建数据库（清空现有数据）
    """
    print("="*80)
    print("RAG知识库构建工具")
    print("="*80)
    
    # 检查文档目录
    if not os.path.exists(documents_dir):
        print(f"❌ 错误：文档目录不存在: {documents_dir}")
        return False
    
    # 统计文档数量
    md_files = list(Path(documents_dir).glob("*.md"))
    print(f"\n📁 文档目录: {documents_dir}")
    print(f"📄 找到 {len(md_files)} 个markdown文件")
    
    if len(md_files) == 0:
        print("❌ 错误：没有找到markdown文件")
        return False
    
    # 初始化向量存储
    print(f"\n💾 初始化向量数据库: {db_path}")
    vector_store = VectorStore(
        persist_directory=db_path,
        collection_name="security_knowledge",
        embedding_model="nomic-embed-text"
    )
    
    # 如果需要重建，清空现有数据
    if rebuild and vector_store.collection.count() > 0:
        print("\n🗑️  重建模式：清空现有数据...")
        vector_store.delete_all()
    
    # 检查是否已有数据
    current_count = vector_store.collection.count()
    if current_count > 0:
        print(f"\n⚠️  数据库已包含 {current_count} 个文档")
        response = input("是否继续添加？(y/n): ")
        if response.lower() != 'y':
            print("取消操作")
            return False
    
    # 初始化RAG检索器
    print("\n🔧 初始化RAG检索器...")
    rag_retriever = RAGRetriever(
        vector_store=vector_store,
        chunk_size=1000,
        chunk_overlap=200
    )
    
    # 索引文档
    print("\n📚 开始索引文档...")
    print("-"*80)
    try:
        rag_retriever.index_documents(documents_dir)
        print("-"*80)
        print("\n✅ 知识库构建完成！")
        
        # 显示统计信息
        stats = rag_retriever.get_stats()
        print("\n📊 知识库统计:")
        print(f"   - 集合名称: {stats['collection_name']}")
        print(f"   - 文档块数: {stats['document_count']}")
        print(f"   - 存储路径: {stats['persist_directory']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search(db_path: str = "./chroma_db"):
    """测试搜索功能"""
    print("\n" + "="*80)
    print("测试搜索功能")
    print("="*80)
    
    # 初始化
    vector_store = VectorStore(
        persist_directory=db_path,
        collection_name="security_knowledge",
        embedding_model="nomic-embed-text"
    )
    
    rag_retriever = RAGRetriever(vector_store=vector_store)
    
    # 测试查询
    test_queries = [
        "CVE-2024-0012",
        "Palo Alto防火墙漏洞",
        "远程命令执行",
        "身份认证绕过"
    ]
    
    for query in test_queries:
        print(f"\n🔍 查询: {query}")
        print("-"*80)
        
        results = rag_retriever.retrieve(query, n_results=2)
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"\n文档 {i}:")
                print(f"  标题: {result['metadata'].get('title', '未知')}")
                print(f"  文件: {result['metadata'].get('filename', '未知')}")
                if 'cve_ids' in result['metadata']:
                    print(f"  CVE: {result['metadata']['cve_ids']}")
                if result['distance']:
                    print(f"  相似度: {1 - result['distance']:.3f}")
                print(f"  内容预览: {result['content'][:200]}...")
        else:
            print("  未找到相关文档")
        
        print("-"*80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="构建RAG知识库")
    parser.add_argument(
        "--docs-dir",
        type=str,
        default="/disk1/users/user/UltraRAG/data/extracted_readmes",
        help="markdown文档目录路径"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="./chroma_db",
        help="向量数据库路径"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="重建数据库（清空现有数据）"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="构建后运行测试搜索"
    )
    
    args = parser.parse_args()
    
    # 构建知识库
    success = build_knowledge_base(
        documents_dir=args.docs_dir,
        db_path=args.db_path,
        rebuild=args.rebuild
    )
    
    # 如果成功且需要测试
    if success and args.test:
        test_search(args.db_path)
    
    print("\n" + "="*80)
    print("完成！")
    print("="*80)
