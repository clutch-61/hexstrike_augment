"""
文档处理模块
负责加载和分块markdown文档
"""

import os
from typing import List, Dict
from pathlib import Path
import hashlib


class DocumentProcessor:
    """处理markdown文档的类"""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        初始化文档处理器
        
        Args:
            chunk_size: 每个文档块的字符数
            chunk_overlap: 块之间的重叠字符数
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def load_markdown_files(self, directory: str) -> List[Dict[str, str]]:
        """
        加载目录中的所有markdown文件
        
        Args:
            directory: markdown文件所在目录
            
        Returns:
            包含文档内容和元数据的字典列表
        """
        documents = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            raise ValueError(f"目录不存在: {directory}")
        
        for file_path in directory_path.glob("*.md"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 提取元数据
                metadata = self._extract_metadata(content, str(file_path))
                
                documents.append({
                    'content': content,
                    'metadata': metadata
                })
                
            except Exception as e:
                print(f"加载文件失败 {file_path}: {e}")
        
        print(f"成功加载 {len(documents)} 个文档")
        return documents
    
    def _extract_metadata(self, content: str, file_path: str) -> Dict[str, str]:
        """
        从markdown内容中提取元数据
        
        Args:
            content: markdown文档内容
            file_path: 文件路径
            
        Returns:
            元数据字典
        """
        metadata = {
            'source': file_path,
            'filename': os.path.basename(file_path)
        }
        
        # 提取标题
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                metadata['title'] = line[2:].strip()
                break
        
        # 提取CVE ID
        cve_ids = []
        for line in lines:
            if 'CVE-' in line:
                # 简单提取CVE ID
                import re
                cves = re.findall(r'CVE-\d{4}-\d{4,7}', line)
                cve_ids.extend(cves)
        
        if cve_ids:
            metadata['cve_ids'] = ', '.join(set(cve_ids))
        
        # 提取来源和日期
        for line in lines:
            if line.startswith('**来源:**'):
                metadata['origin'] = line.replace('**来源:**', '').strip()
            elif line.startswith('**日期:**'):
                metadata['date'] = line.replace('**日期:**', '').strip()
            elif line.startswith('**链接:**'):
                metadata['link'] = line.replace('**链接:**', '').strip()
        
        return metadata
    
    def chunk_documents(self, documents: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        将文档分块
        
        Args:
            documents: 文档列表
            
        Returns:
            分块后的文档列表
        """
        chunked_documents = []
        
        for doc in documents:
            content = doc['content']
            metadata = doc['metadata']
            
            # 按段落分割
            paragraphs = content.split('\n\n')
            
            current_chunk = ""
            chunk_id = 0
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                # 如果添加当前段落会超过chunk_size
                if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                    # 保存当前chunk
                    chunk_metadata = metadata.copy()
                    chunk_metadata['chunk_id'] = chunk_id
                    chunk_metadata['doc_id'] = self._generate_doc_id(metadata['source'])
                    
                    chunked_documents.append({
                        'content': current_chunk.strip(),
                        'metadata': chunk_metadata
                    })
                    
                    # 开始新chunk，保留重叠部分
                    overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                    current_chunk = overlap_text + '\n\n' + para
                    chunk_id += 1
                else:
                    if current_chunk:
                        current_chunk += '\n\n' + para
                    else:
                        current_chunk = para
            
            # 保存最后一个chunk
            if current_chunk:
                chunk_metadata = metadata.copy()
                chunk_metadata['chunk_id'] = chunk_id
                chunk_metadata['doc_id'] = self._generate_doc_id(metadata['source'])
                
                chunked_documents.append({
                    'content': current_chunk.strip(),
                    'metadata': chunk_metadata
                })
        
        print(f"文档分块完成: {len(documents)} 个文档 -> {len(chunked_documents)} 个块")
        return chunked_documents
    
    def _generate_doc_id(self, source: str) -> str:
        """生成文档ID"""
        return hashlib.md5(source.encode()).hexdigest()[:16]
