import gradio as gr
from resume_chromadb_operater import add_resume, delete_resume, query_resume, similarity_search as resume_similarity_search, batch_add_resumes
from job_chromadb_operater import add_job, delete_job, query_job, similarity_search as job_similarity_search, batch_add_jobs
import json
import numpy as np

def add_resume_ui(name, stu_id, resume_content):
    """添加简历的UI处理函数"""
    resume_data = {
        "name": name,
        "stu_ids": stu_id,
        "resume_content": resume_content
    }
    success = add_resume(resume_data)
    if success:
        return "简历添加成功！"
    return "简历添加失败，请检查输入数据。"

def delete_resume_ui(stu_id):
    """删除简历的UI处理函数"""
    success = delete_resume(stu_id)
    if success:
        return "简历删除成功！"
    return "简历删除失败，请检查学号是否存在。"

def query_resume_ui(stu_id):
    """查询简历的UI处理函数"""
    result = query_resume(stu_id)
    if result:
        return f"学生姓名：{result['metadata']['name']}\n\n简历内容：\n{result['content']}"
    return "未找到对应学号的简历信息。"

def search_similar_resumes_by_job(company_name, job_id, job_requirements, job_responsibilities, major="", job_url="", num_results=10):
    """根据岗位信息搜索匹配的简历
    Args:
        company_name: str, 公司名称
        job_id: str, 岗位ID
        job_requirements: str, 岗位要求
        job_responsibilities: str, 岗位职责
        major: str, 专业要求，默认为空
        job_url: str, 岗位链接，默认为空
        num_results: int, 返回结果数量，默认10条
    Returns:
        str: 格式化的匹配结果
    """
    # 组合查询文本
    query_text = f"{job_requirements} {job_responsibilities} {major}".strip()
    
    # 调用简历库的相似度搜索
    results = resume_similarity_search(query_text, n_results=num_results)
    
    if results and results['documents']:
        output = f"为 {company_name}（岗位ID：{job_id}）匹配到的推荐简历：\n"
        output += "-" * 50 + "\n"
        
        for i, (doc, meta, distance) in enumerate(zip(
            results['documents'][0], 
            results['metadatas'][0],
            results['distances'][0]
        )):
            match_score = map_distance_to_score(distance)  # 将距离转换为相似度分数
            
            output += f"\n=== 推荐简历 {i+1} (匹配度: {match_score:.1f}%) ===\n"
            output += f"学生姓名：{meta['name']}\n"
            output += f"学号：{meta['stu_id']}\n"
            output += f"简历内容：\n{doc}\n"
            output += "-" * 30 + "\n"
        return output
    return f"未找到与该岗位匹配的简历。"

def add_job_ui(company_name, job_id, major, job_url, requirements, responsibilities):
    """添加岗位的UI处理函数"""
    job_data = {
        "company_name": company_name,
        "job_id": job_id,
        "major": major,
        "job_url": job_url,
        "job_requirements": requirements,
        "job_responsibilities": responsibilities
    }
    success = add_job(job_data)
    if success:
        return "岗位添加成功！"
    return "岗位添加失败，请检查输入数据。"

def delete_job_ui(job_id):
    """删除岗位的UI处理函数"""
    success = delete_job(job_id)
    if success:
        return "岗位删除成功！"
    return "岗位删除失败，请检查岗位ID是否存在。"

def query_job_ui(job_id):
    """查询岗位的UI处理函数"""
    result = query_job(job_id)
    if result:
        return f"公司名称：{result['metadata']['company_name']}\n" \
               f"专业要求：{result['metadata']['major']}\n" \
               f"岗位链接：{result['metadata']['job_url']}\n\n" \
               f"岗位详情：\n{result['content']}"
    return "未找到对应岗位ID的信息。"

def search_similar_jobs_by_resume(name, stu_id, resume_content, num_results=10):
    """根据简历内容搜索匹配的岗位
    Args:
        name: str, 学生姓名
        stu_id: str, 学号
        resume_content: str, 简历内容
        num_results: int, 返回结果数量，默认10条
    Returns:
        str: 格式化的匹配结果
    """
    results = job_similarity_search(resume_content, n_results=num_results)
    if results and results['documents']:
        output = f"为 {name}（学号：{stu_id}）匹配到的推荐岗位：\n"
        output += "-" * 50 + "\n"
        
        for i, (doc, meta, distance) in enumerate(zip(
            results['documents'][0], 
            results['metadatas'][0],
            results['distances'][0]
        )):
            match_score = map_distance_to_score(distance)  # 将距离转换为相似度分数
            
            output += f"\n=== 推荐岗位 {i+1} (匹配度: {match_score:.1f}%) ===\n"
            output += f"公司名称：{meta['company_name']}\n"
            output += f"岗位ID：{meta['job_id']}\n"
            output += f"专业要求：{meta['major']}\n"
            output += f"岗位链接：{meta['job_url']}\n"
            output += f"岗位详情：\n{doc}\n"
            output += "-" * 30 + "\n"
        return output
    return f"未找到与 {name} 简历匹配的岗位。"

def handle_resume_json_upload(file):
    """处理简历JSON文件上传"""
    try:
        if file is None:
            return "请选择要上传的文件"
            
        if isinstance(file, list):
            file = file[0]  # Gradio可能返回文件列表
            
        if hasattr(file, "name"):  # 新版本Gradio
            with open(file.name, "r", encoding="utf-8") as f:
                resume_data = json.load(f)
        else:  # 兼容处理
            content = file.decode('utf-8')
            resume_data = json.loads(content)
            
        success_count = batch_add_resumes(resume_data)
        return f"成功导入 {success_count} 份简历"
    except Exception as e:
        return f"导入失败：{str(e)}"

def handle_job_json_upload(file):
    """处理岗位JSON文件上传"""
    try:
        if file is None:
            return "请选择要上传的文件"
            
        if isinstance(file, list):
            file = file[0]  # Gradio可能返回文件列表
            
        if hasattr(file, "name"):  # 新版本Gradio
            with open(file.name, "r", encoding="utf-8") as f:
                job_data = json.load(f)
        else:  # 兼容处理
            content = file.decode('utf-8')
            job_data = json.loads(content)
            
        success_count = batch_add_jobs(job_data)
        return f"成功导入 {success_count} 个岗位"
    except Exception as e:
        return f"导入失败：{str(e)}"

# 创建Gradio界面
with gr.Blocks(title="润小职Agent青春版") as demo:
    gr.Markdown("## 润小职Agent青春版")
    
    with gr.Tab("添加简历"):
        gr.Markdown("### 方式一：单个添加")
        with gr.Row():
            name_input = gr.Textbox(label="学生姓名")
            stu_id_input = gr.Textbox(label="学号")
        resume_content = gr.Textbox(label="简历内容", lines=10)
        add_btn = gr.Button("添加简历")
        add_output = gr.Textbox(label="添加结果")
        add_btn.click(add_resume_ui, 
                     inputs=[name_input, stu_id_input, resume_content],
                     outputs=add_output)
        
        gr.Markdown("### 方式二：批量导入")
        with gr.Row():
            resume_file_input = gr.File(label="上传JSON文件", file_types=[".json"])
            resume_upload_output = gr.Textbox(label="导入结果")
        resume_file_input.change(handle_resume_json_upload,
                               inputs=[resume_file_input],
                               outputs=resume_upload_output)
    
    with gr.Tab("删除简历"):
        delete_stu_id = gr.Textbox(label="要删除的学号")
        delete_btn = gr.Button("删除简历")
        delete_output = gr.Textbox(label="删除结果")
        delete_btn.click(delete_resume_ui, 
                        inputs=delete_stu_id,
                        outputs=delete_output)
    
    with gr.Tab("查询简历"):
        query_stu_id = gr.Textbox(label="要查询的学号")
        query_btn = gr.Button("查询简历")
        query_output = gr.Textbox(label="查询结果", lines=10)
        query_btn.click(query_resume_ui,
                       inputs=query_stu_id,
                       outputs=query_output)
    
    with gr.Tab("岗位->简历匹配"):
        with gr.Row():
            job_company_name = gr.Textbox(label="公司名称")
            job_id_input = gr.Textbox(label="岗位ID")
        with gr.Row():
            job_major = gr.Textbox(label="专业要求")
            job_url_input = gr.Textbox(label="岗位链接", value="")
        job_requirements = gr.Textbox(label="岗位要求", lines=5)
        job_responsibilities = gr.Textbox(label="岗位职责", lines=5)
        match_resumes_btn = gr.Button("匹配简历")
        match_resumes_output = gr.Textbox(label="匹配结果", lines=20)
        match_resumes_btn.click(search_similar_resumes_by_job,
                            inputs=[job_company_name, job_id_input, job_requirements, 
                                    job_responsibilities, job_major, job_url_input],
                            outputs=match_resumes_output)
    
    with gr.Tab("添加岗位"):
        gr.Markdown("### 方式一：单个添加")
        with gr.Row():
            company_name = gr.Textbox(label="公司名称")
            job_id = gr.Textbox(label="岗位ID")
        with gr.Row():
            major = gr.Textbox(label="专业要求")
            job_url = gr.Textbox(label="岗位链接")
        requirements = gr.Textbox(label="岗位要求", lines=5)
        responsibilities = gr.Textbox(label="岗位职责", lines=5)
        add_job_btn = gr.Button("添加岗位")
        add_job_output = gr.Textbox(label="添加结果")
        add_job_btn.click(add_job_ui,
                         inputs=[company_name, job_id, major, job_url, requirements, responsibilities],
                         outputs=add_job_output)
        
        gr.Markdown("### 方式二：批量导入")
        with gr.Row():
            job_file_input = gr.File(label="上传JSON文件", file_types=[".json"])
            job_upload_output = gr.Textbox(label="导入结果")
        job_file_input.change(handle_job_json_upload,
                            inputs=[job_file_input],
                            outputs=job_upload_output)
    
    with gr.Tab("删除岗位"):
        delete_job_id = gr.Textbox(label="要删除的岗位ID")
        delete_job_btn = gr.Button("删除岗位")
        delete_job_output = gr.Textbox(label="删除结果")
        delete_job_btn.click(delete_job_ui,
                           inputs=delete_job_id,
                           outputs=delete_job_output)
    
    with gr.Tab("查询岗位"):
        query_job_id = gr.Textbox(label="要查询的岗位ID")
        query_job_btn = gr.Button("查询岗位")
        query_job_output = gr.Textbox(label="查询结果", lines=10)
        query_job_btn.click(query_job_ui,
                          inputs=query_job_id,
                          outputs=query_job_output)
    

            
    with gr.Tab("简历->岗位匹配"):
        with gr.Row():
            resume_name = gr.Textbox(label="学生姓名")
            resume_id = gr.Textbox(label="学号")
        resume_text = gr.Textbox(label="简历内容", lines=10)
        match_btn = gr.Button("匹配岗位")
        match_output = gr.Textbox(label="匹配结果", lines=20)
        match_btn.click(search_similar_jobs_by_resume,
                   inputs=[resume_name, resume_id, resume_text],
                   outputs=match_output)
def map_distance_to_score(distance):
    """将余弦距离映射到45-95的分数区间，使用sigmoid函数实现非线性映射
    - 分数主要集中在55-85区间
    - 45-55和85-95各占约15%的比例
    """
    # 首先将distance转换为初始分数
    raw_score = (1 - distance) * 100
    
    # 使用sigmoid函数进行非线性映射
    def sigmoid(x, k=0.15):
        return 1 / (1 + np.exp(-k * (x - 50)))
    
    # 映射到45-95区间
    mapped_score = 45 + 50 * sigmoid(raw_score)
    return mapped_score


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
