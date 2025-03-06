from chromadb.utils import embedding_functions
import chromadb
import json
current_job_id = 22339

# 创建 BGE 中文嵌入模型实例
bge_embedding = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-large-zh-v1.5"
)


# 1. 创建 ChromaDB collection
client = chromadb.PersistentClient(path="./chroma_data")
collection = client.create_collection(
    name="jobs",
    embedding_function=bge_embedding,
    metadata={"dimensionality": 1024}  # BGE-large 模型的输出维度
    )

# 2. 处理JSON数据
def process_jobs(jobs):
    global current_job_id
    for job in jobs:
        # 合并职责和要求作为文本内容
        text = f"{job.get('job_requirements', '')} {job.get('job_responsibilities', '')}"
  # 如果没有job_id，使用自增长的id

        job_id = str(job.get("job_id", ""))
        if not job_id:
            job_id = str(current_job_id)
            current_job_id += 1       
        # 元数据
        metadata = {
            "company_name": job.get("company_name", ""),
            "major": job.get("major", ""),
            "job_id": job_id, 
            "job_url": job.get("job_url", "")
        }
        
        # 添加到collection
        if text.strip():
            collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[job_id]
            )

# 3. 处理三个JSON文件
with open("campus_talk_data.json",encoding='utf-8') as f:
    data = json.load(f)
    process_jobs(data["jobs"])

with open("onlien_recruitment_data.json",encoding='utf-8') as f:
    data = json.load(f)
    process_jobs(data["jobs"])
    
with open("jobfair_22339_data.json",encoding='utf-8') as f:
    data = json.load(f)  
    process_jobs(data["jobs"])

print("Done!")
job_ids = [2487507, 2487506, 2494720]
for job_id in job_ids:
    try:
        # 获取元数据和嵌入向量
        result = collection.get(
            ids=[str(job_id)],  # 将ID转换为字符串并放入列表
            include=['metadatas', 'embeddings', 'documents']
        )
        
        print(f"\nJob ID: {job_id}")
        
        # 打印元数据
        if result['metadatas'] and len(result['metadatas']) > 0:
            print("元数据:")
            print(result['metadatas'][0])
        else:
            print(f"未找到ID为 {job_id} 的元数据")
            
        # 打印嵌入向量
        if result['embeddings'] and len(result['embeddings']) > 0:
            print("嵌入向量 (前10个维度):")
            print(result['embeddings'][0][:10])
            print(f"向量维度: {len(result['embeddings'][0])}")
        else:
            print(f"未找到ID为 {job_id} 的嵌入向量")
            
    except Exception as e:
        print(f"获取数据时发生错误: {e}")