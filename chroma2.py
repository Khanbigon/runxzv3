from chromadb.utils import embedding_functions
import chromadb
import json


# 创建 BGE 中文嵌入模型实例
bge_embedding = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-large-zh-v1.5"
)


# 1. 创建 ChromaDB collection
client = chromadb.PersistentClient(path="./chroma_resume_data")
collection = client.create_collection(
    name="resumes",
    embedding_function=bge_embedding,
    metadata={"dimensionality": 1024}  # BGE-large 模型的输出维度
    )

# 2. 处理JSON数据
def process_resumes(resumes):
    for resume in resumes:
        # 获取文本内容
        text = resume.get('resume_content', '')
  
        # 元数据
        resumes_metadata = {
            "name": resume.get("name", ""),
            "stu_id": resume.get("stu_ids", ""), 
        }
        stu_id = str(resume.get("stu_ids", ""))   
        # 添加到collection
        if text.strip():
            collection.add(
                documents=[text],
                metadatas=[resumes_metadata],
                ids=[stu_id]
            )

# 3. 处理JSON文件
with open("resumes.json",encoding='utf-8') as f:
    resumes = json.load(f)
    process_resumes(resumes)


print("Done!")
stu_ids = [202100701018, 202100202141]
for stu_id in stu_ids:
    try:
        # 获取元数据和嵌入向量
        result = collection.get(
            ids=[str(stu_id)],  # 将ID转换为字符串并放入列表
            include=['metadatas', 'embeddings', 'documents']
        )
        
        print(f"\nstu ID: {stu_id}")
        
         # 打印元数据
        if result['metadatas'] and len(result['metadatas']) > 0:
            print("元数据:")
            print(result['metadatas'][0])
        else:
            print(f"未找到ID为 {stu_id} 的元数据")
            
        # 打印嵌入向量
        if result['embeddings'] and len(result['embeddings']) > 0:
            print("嵌入向量 (前10个维度):")
            print(result['embeddings'][0][:10])
            print(f"向量维度: {len(result['embeddings'][0])}")
        else:
            print(f"未找到ID为 {stu_id} 的嵌入向量")
            
    except Exception as e:
        print(f"获取数据时发生错误: {e}")