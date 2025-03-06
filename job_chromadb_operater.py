from chromadb.utils import embedding_functions  
import chromadb
import json

# 创建 BGE 中文嵌入模型实例
bge_embedding = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-large-zh-v1.5"
)

# 连接到已有的 ChromaDB collection
client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_collection(
    name="jobs",
    embedding_function=bge_embedding
)

def add_job(job_data):
    """添加工作信息到数据库"""
    # 合并职责和要求作为文本内容
    text = f"{job_data.get('job_requirements', '')} {job_data.get('job_responsibilities', '')}"
    
    # 元数据 
    metadata = {
        "company_name": job_data.get("company_name", ""),
        "major": job_data.get("major", ""),
        "job_id": job_data.get("job_id", ""),
        "job_url": job_data.get("job_url", "")
    }
    
    job_id = str(job_data.get("job_id", ""))
    
    # 添加到collection
    if text.strip():
        try:
            collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[job_id]
            )
            return True
        except Exception as e:
            print(f"添加工作信息失败: {e}")
            return False

def delete_job(job_id):
    """根据job_id删除工作信息"""
    try:
        collection.delete(ids=[str(job_id)])
        return True
    except Exception as e:
        print(f"删除工作信息失败: {e}")
        return False

def query_job(job_id):
    """根据job_id查询工作信息"""
    try:
        result = collection.get(
            ids=[str(job_id)],
            include=['metadatas', 'documents']
        )
        
        if result['metadatas'] and result['documents']:
            return {
                'metadata': result['metadatas'][0],
                'content': result['documents'][0]
            }
        return None
    except Exception as e:
        print(f"查询工作信息失败: {e}")
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

def batch_add_jobs(jobs_data):
    """批量添加工作信息"""
    success_count = 0
    for job in jobs_data.get("jobs", []):
        if add_job(job):
            success_count += 1
    return success_count

if __name__ == "__main__":
    # 测试添加
    test_job = {
        "company_name": "测试公司",
        "job_requirements": "测试要求",
        "job_responsibilities": "测试职责",
        "major": "不限",
        "job_id": "999999",
        "job_url": "http://test.com"
    }
    print("添加测试:", add_job(test_job))
    
    # 测试查询
    print("查询测试:", query_job("999999"))
    
    # 测试相似搜索
    print("相似搜索测试:", similarity_search("测试职责要求"))
    
    # 测试删除
    print("删除测试:", delete_job("999999"))