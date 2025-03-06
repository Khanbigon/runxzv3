from chromadb.utils import embedding_functions  
import chromadb
import json

# 创建 BGE 中文嵌入模型实例
bge_embedding = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-large-zh-v1.5"
)

# 连接到已有的 ChromaDB collection
client = chromadb.PersistentClient(path="./chroma_resume_data")
collection = client.get_collection(
    name="resumes",
    embedding_function=bge_embedding
)

def add_resume(resume_data):
    """添加简历到数据库"""
    text = resume_data.get('resume_content', '')
    
    # 元数据
    resume_metadata = {
        "name": resume_data.get("name", ""),
        "stu_id": resume_data.get("stu_ids", "")
    }
    
    # 将ID转换为字符串
    stu_id = str(resume_data.get("stu_ids", ""))
    
    # 添加到collection
    if text.strip():
        try:
            collection.add(
                documents=[text],
                metadatas=[resume_metadata], 
                ids=[stu_id]
            )
            return True
        except Exception as e:
            print(f"添加简历失败: {e}")
            return False

def delete_resume(stu_id):
    """根据学号删除简历"""
    try:
        collection.delete(ids=[str(stu_id)])
        return True
    except Exception as e:
        print(f"删除简历失败: {e}")
        return False

def query_resume(stu_id):
    """根据学号查询简历"""
    try:
        result = collection.get(
            ids=[str(stu_id)],
            include=['metadatas', 'documents']
        )
        
        if result['metadatas'] and result['documents']:
            return {
                'metadata': result['metadatas'][0],
                'content': result['documents'][0]
            }
        return None
    except Exception as e:
        print(f"查询简历失败: {e}")
        return None

def similarity_search(query_text, n_results=5):
    """相似度搜索"""
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=['metadatas', 'documents', 'distances']
        )
        return results
    except Exception as e:
        print(f"相似度搜索失败: {e}")
        return None

if __name__ == "__main__":
    # 测试添加
    test_resume = {
        "name": "测试",
        "stu_ids": "202500000001", 
        "resume_content": "这是一份测试简历"
    }
    print("添加测试:", add_resume(test_resume))
    
    # 测试查询
    print("查询测试:", query_resume("202500000001"))
    
    # 测试相似度搜索
    print("相似搜索测试:", similarity_search("测试简历"))
    
    # 测试删除
    print("删除测试:", delete_resume("202500000001"))