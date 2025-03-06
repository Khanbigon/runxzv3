import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
import json

def match_jobs_for_resume(resume_data):
    # 初始化模型
    model = SentenceTransformer("BAAI/bge-large-zh-v1.5")
    
    # 从resume_data中获取信息
    name = resume_data["name"]
    stu_id = resume_data["stu_ids"]
    resume_content = resume_data["resume_content"]
    
    # 生成简历文本的嵌入向量
    resume_embedding = model.encode([resume_content], normalize_embeddings=True)
    
    # 初始化持久化客户端并获取collection
    client = chromadb.PersistentClient(path="./chroma_data")
    collection = client.get_collection(name="jobs")
    
    # 查询最相似的10个岗位
    results = collection.query(
        query_embeddings=resume_embedding.tolist(),
        n_results=10,
        include=["metadatas", "documents", "distances"]  # 添加 metadatas
    )
    
    # 构建输出的JSON格式
    output = {
        "name": name,
        "stu_id": stu_id,
        "resume_content": resume_content,
        "matched_jobs": []
    }
    
    # 整理匹配结果
    for i in range(len(results["ids"][0])):
        job_match = {
            "job_id": results["ids"][0][i],
            "company_name": results["metadatas"][0][i].get("company_name", ""),  # 获取公司名称
            "job_url": results["metadatas"][0][i].get("job_url", ""),  # 获取职位URL
            "distance": float(results["distances"][0][i]),  # 转换为Python float类型以便JSON序列化
            "document": results["documents"][0][i]
        }
        output["matched_jobs"].append(job_match)
    
    return output

# 读取简历数据
with open("resumes.json", "r", encoding="utf-8") as f:
    resumes = json.load(f)

# 处理所有简历并保存结果
all_results = []
for resume in resumes:
    result = match_jobs_for_resume(resume)
    all_results.append(result)

# 将结果保存为JSON文件
with open("match_results.json", "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

print("匹配完成，结果已保存到 match_results.json")