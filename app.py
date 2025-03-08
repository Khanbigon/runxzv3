import gradio as gr
import pandas as pd
import json
from openai import OpenAI
import time
import re
import threading
from datetime import datetime
from uuid import uuid4
from job_chromadb_operater import query_job, add_job, delete_job, similarity_search as job_similarity_search
from resume_chromadb_operater import query_resume, add_resume, delete_resume, similarity_search as resume_similarity_search
import os
import hashlib
import requests
# 大模型配置
client = OpenAI(
    api_key="sk-430766cb68934151aaeae540823fea2f",
    base_url="https://api.deepseek.com"
)

# 新增定时任务相关配置
UPDATE_INTERVAL = 3600  # 1小时更新一次（单位：秒）
last_update_time = None
update_running = True

# 全局缓存
job_data = None
CACHE_EXPIRY = 300

# 大模型匹配函数
def get_matching_score(student_skills, job_requirements):
    prompt = f"""请根据以下学生技能和企业岗位要求进行匹配度评分（0-100），并列出关键匹配点：
请基于以下规则评分：
1. 技能关键词匹配度（如"Python" vs "Python编程"）
2. 技能相关性（如"数据分析" vs "数据可视化"）
3. 综合能力覆盖度
学生技能：
{student_skills}
岗位要求：
{job_requirements}
输出JSON格式：{{"score": 分数, "matches": ["匹配点1", "匹配点2"]}}"""
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"大模型调用失败: {e}")
        return {"score": 0, "matches": []}

# 解析薪资字符串为最低和最高薪资
def parse_salary(salary_str):
    if not salary_str:
        return 0, 0
    match = re.search(r'(\d+)[kK]-(\d+)[kK]', salary_str)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0

def fetch_data():
    # 模拟数据爬取逻辑（需替换为真实爬虫）
    global job_data, last_update_time
    try:
        print(f"[{datetime.now()}] 开始数据更新...")
        # 这里应添加实际的数据爬取代码
        # 模拟数据更新
        
        with open("job.json", 'r', encoding='utf-8') as f:
            job_data = json.load(f)
        
        last_update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{last_update_time}] 数据更新完成！")
        return True
    except Exception as e:
        print(f"数据更新失败: {str(e)}")
        return False

def auto_update_task():
    while update_running:
        fetch_data()
        time.sleep(UPDATE_INTERVAL)

# 启动自动更新线程
update_thread = threading.Thread(target=auto_update_task, daemon=True)
update_thread.start()

def process_resume_form(name, student_id, mobile, education, major, skills, projects, internships):
    if not name or not student_id:
        return "请填写姓名和学号", None
    
    # 构建简历JSON结构
    resume_data = {
        "name": name,
        "index": student_id,
        "mobile": mobile,
        "metadata": {  # 添加元数据字段
        "student_id": student_id,
        "mobile": mobile,
        "source": "form"
    },
        "resume_content": f"""
教育背景：{education}
专业：{major}
技能：{skills}
项目经历：{projects}
实习经历：{internships}
手机号：{mobile}
        """
    }
    
    # 保存到临时文件
    temp_file = f"temp_resume_{student_id}.json"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(resume_data, f, ensure_ascii=False, indent=2)
    
    # 添加到向量数据库
    try:
        add_result = add_resume(resume_data)
        return f"简历信息已保存", temp_file
    except Exception as e:
        return f"简历保存失败: {str(e)}", temp_file


RESUME_PROMPT = """请根据以下简历内容，提供专业优化建议。分析重点包括：
1. 结构完整性（基本信息、教育背景、技能、项目经历等）
2. 关键词使用与目标岗位的匹配度
3. 内容量化成果和具体案例
4. 语言表达的专业性和简洁性
5. 格式规范性和易读性

简历内容：
{resume_content}

请按以下JSON格式返回分析结果：
{{
  "score": 总体评分(0-100),
  "strengths": ["优势1", "优势2"],
  "improvements": ["建议1", "建议2", "建议3"]
}}"""

def get_resume_feedback(resume_content):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{
                "role": "user",
                "content": RESUME_PROMPT.format(resume_content=resume_content)
            }],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        return {
            "score": 0,
            "strengths": [],
            "improvements": [f"分析失败：{str(e)}"]
        }

def get_resume_content(resume_file, form_file):
    try:
        content = None
        # 优先使用表单生成的简历文件
        if form_file and os.path.exists(form_file):
            with open(form_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                content = data.get('resume_content', '')
        
        # 其次使用上传的简历文件
        if not content and resume_file:
            if isinstance(resume_file, str):  # 处理文件路径
                with open(resume_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:  # 处理上传文件对象
                with open(resume_file.name, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            content = data.get('resume_content', '')
            
        if not content:
            return "请先填写或上传简历"
            
        return content
    except json.JSONDecodeError:
        return "简历文件格式错误"
    except Exception as e:
        print(f"简历内容提取失败: {str(e)}")
        return "简历解析失败，请检查文件格式"


def format_feedback_html(result):

    if not isinstance(result, dict):
        return f"<div style='color:red'>无效的返回格式：{type(result)}</div>"

    loading_html = """
    <div style="text-align:center; padding:20px;">
        <div class="loader"></div>
        <p style="color:#666;">正在生成优化建议...</p>
    </div>
    <style>
    .loader {
        border: 5px solid #f3f3f3;
        border-radius: 50%;
        border-top: 5px solid #3498db;
        width: 50px;
        height: 50px;
        animation: spin 1s linear infinite;
        margin: 0 auto;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    """
    
    # 错误处理
    if "improvements" not in result:
        return f"""<div style="color:red; padding:20px;">
            <h4>⚠️ 分析失败</h4>
            <p>{result.get('error', '未知错误')}</p>
        </div>"""

    # 正常处理
    html = f"""
    <div style="font-family: 'Segoe UI'; padding: 20px; background: #f8f9fa; border-radius: 10px;">
        <div style="display: flex; align-items: center; margin-bottom: 20px;">
            <h3 style="margin: 0; color: #003788;">简历综合评分：</h3>
            <div style="margin-left: 15px; width: 60px; height: 60px; background: {get_score_color(result['score'])};
                     border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                <span style="color: white; font-weight: bold; font-size: 18px;">{result['score']}</span>
            </div>
        </div>
         
        <div style="background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
            <h4 style="color: #27ae60; margin-top: 0;">✓ 简历优势</h4>
            <ul style="color: #2c3e50;">
                {"".join([f"<li>{s}</li>" for s in result['strengths']])}
            </ul>
        </div>
        
        <div style="background: white; padding: 20px; border-radius: 10px;">
            <h4 style="color: #e74c3c; margin-top: 0;">✎ 优化建议</h4>
            <ol style="color: #2c3e50;">
                {"".join([f"<li>{i}</li>" for i in result['improvements']])}
            </ol>
        </div>
    </div>
    """
    return html

# 批量匹配处理
def batch_match_process(resume_file, job_file=None, top_n=3):
    global job_data
    progress = gr.Progress()
    
    # 解析简历文件
    progress(0.1, desc="解析学生简历...")
    try:
        with open(resume_file.name, 'r', encoding='utf-8') as f:
            resumes = json.load(f)
    except Exception as e:
        return f"简历文件解析失败: {str(e)}", None
    
    # 加载岗位数据
    progress(0.2, desc="加载岗位数据...")
    if job_file:
        try:
            with open(job_file.name, 'r', encoding='utf-8') as f:
                job_data = json.load(f)
        except Exception as e:
            return f"岗位文件解析失败: {str(e)}", None
    elif not job_data:
        return "岗位数据未加载，请上传岗位文件或点击更新数据按钮", None
    
    progress(0.3, desc="准备匹配...")
    all_matches = []
    total_students = len(resumes)
    
    # 遍历每个学生的简历
    for idx, student in enumerate(resumes):
        student_name = student.get('name', f'学生{idx+1}')
        student_id = student.get('index', '')
        student_mobile = student.get('mobile', '')
        student_resume = student.get('resume_content', '')
        
        progress(0.3 + 0.6 * (idx/total_students), desc=f"({idx+1}/{total_students})...")
        
        # 为每个学生匹配岗位
        student_matches = []
        
        for job in job_data['jobs']:
            job_id = job.get('job_id', '')
            company_name = job.get('company_name', '')
            job_url = job.get('job_url', '')
            job_requirements = job.get('job_requirements', '')
            job_responsibilities = job.get('job_responsibilities', '')
            
            # 调用大模型进行匹配评分
            match_result = get_matching_score(
                student_resume,
                f"{job_responsibilities}\n{job_requirements}"
            )
            
            # 存储匹配结果
            student_matches.append({
                "job_id": job_id,
                "company_name": company_name,
                "job_url": job_url,
                "score": match_result['score'],
                "document": f"{job_requirements}\n{job_responsibilities}"
            })
            
        # 对该学生的匹配结果排序，选择最佳的top_n个
        student_matches.sort(key=lambda x: x['score'], reverse=True)
        top_matches = student_matches[:top_n]
        
        all_matches.append({
            "name": student_name,
            "stu_id": student_id,
            "mobile": student_mobile,
            "resume_content": student_resume,
            "matched_jobs": top_matches
        })
    
    # 生成匹配结果JSON
    progress(0.95, desc="生成匹配结果...")
    result_json = json.dumps(all_matches, ensure_ascii=False, indent=2)
    
    # 生成可下载的匹配结果文件
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    result_file_name = f"match_result_{timestamp}.json"
    with open(result_file_name, 'w', encoding='utf-8') as f:
        f.write(result_json)
    
    progress(1.0, desc="匹配完成！")
    return build_batch_results_html(all_matches), result_file_name

def manual_update():
    success = fetch_data()
    return gr.update(
        value=f"最后更新：{last_update_time}" if success else "更新失败！",
        visible=True
    )

def get_student_mobile(student_id):
    """
    根据学号获取学生手机号
    从学生简历中提取手机号
    
    参数:
    student_id: 学生学号
    
    返回:
    str: 学生手机号
    """
    try:
        # 1. 优先从向量数据库查询
        from resume_chromadb_operater import query_resume
        resume_data = query_resume(student_id)
        if resume_data and resume_data.get("metadata", {}).get("mobile"):
            return resume_data["metadata"]["mobile"]

        # 2. 尝试从匹配结果文件中查询
        for file in os.listdir():
            if file.startswith("match_result_") and file.endswith(".json"):
                with open(file, 'r', encoding='utf-8') as f:
                    match_results = json.load(f)
                    for student in match_results:
                        if student.get('stu_id') == student_id:
                            # 如果匹配结果中有手机号字段
                            if 'mobile' in student and student['mobile']:
                                return student['mobile']
        
        # 2. 尝试从临时文件中查询
        temp_file = f"temp_resume_{student_id}.json"
        if os.path.exists(temp_file):
            with open(temp_file, 'r', encoding='utf-8') as f:
                resume_data = json.load(f)
                if 'mobile' in resume_data and resume_data['mobile']:
                    return resume_data['mobile']
        
        # 3. 尝试从向量数据库中查询
        try:
            from resume_chromadb_operater import query_resume
            resume_data = query_resume(student_id)
            if resume_data and 'mobile' in resume_data and resume_data['mobile']:
                return resume_data['mobile']
        except Exception as e:
            print(f"从向量数据库查询手机号失败: {str(e)}")
        
        # 4. 从简历内容中提取手机号
        # 尝试从临时文件中的简历内容提取
        if os.path.exists(temp_file):
            with open(temp_file, 'r', encoding='utf-8') as f:
                resume_data = json.load(f)
                content = resume_data.get('resume_content', '')
                # 使用正则表达式匹配手机号
                mobile_match = re.search(r'1[3-9]\d{9}', content)
                if mobile_match:
                    return mobile_match.group(0)
        
        # 5. 如果以上方法都失败，返回默认手机号
        print(f"未能找到学号 {student_id} 的手机号，使用默认号码")
        return "13723728369"  # 默认手机号
    except Exception as e:
        print(f"获取手机号时出错: {str(e)}")
        return "13723728369"  # 出错时返回默认手机号

# 短信发送函数
def send_sms(mobile, content, sign="深圳技术大学"):
    """发送短信的函数
    
    Args:
        mobile: 接收短信的手机号
        content: 短信内容 (不含签名)
        sign: 短信签名
    
    Returns:
        dict: 包含发送状态和消息的字典
    """
    try:
        # 验证手机号格式
        if not mobile or not re.match(r'^1[3-9]\d{9}$', str(mobile)):
            return {"success": False, "message": f"无效的手机号: {mobile}"}
        # 目标接口URL和参数
        password = "92053811"
        post_url = "http://10.1.12.218:8088/websms/smsJsonService"
        md5 = hashlib.md5(password.encode('utf-8')).hexdigest()
        
        # 构建完整短信内容
        full_content = f"【{sign}】{content}"
        
        post_data = {
            "action": "sendsms",
            "userId": "xsjyzdzx",  # 企业帐号
            "md5password": md5,  # 企业密码
            "content": full_content,
            "mobile": str(mobile),
        }
        print(f"发送短信请求: {post_data}")
        response = requests.post(post_url, data=post_data)
        result = response.text
        print(f"短信发送响应: {result}")
        
        # 检查响应是否包含成功信息
        if "success" in result.lower() or "成功" in result:
            return {"success": True, "message": "短信发送成功", "response": result}
        else:
            return {"success": False, "message": f"短信发送失败: {result}", "response": result}
    except Exception as e:
        print(f"短信发送失败: {str(e)}")
        return {"success": False, "message": f"短信发送失败: {str(e)}"}

# 个人匹配后发送通知
def send_match_notification(student_id=None, current_id=None, result_data=None):
    """发送个人匹配结果通知
    
    Args:
        result_data: 匹配结果数据
        student_id: 学生学号(用于在数据库中查找)
    
    Returns:
        str: 操作结果信息
    """
    # 如果没有直接提供结果数据，尝试通过学号查找
    actual_id = student_id if student_id else current_id
    try:
        # 检查是否提供了学号
        if not actual_id:
            return "请先填写学号或上传简历"
            
        print(f"尝试为学号 {student_id} 发送通知")
        
        # 获取学生手机号
        mobile = get_student_mobile(actual_id)
        
        if not mobile or mobile == "13723728369":  # 检查是否为默认手机号
            return "未找到有效的手机号码，请确保已填写手机号"
            
        print(f"获取到手机号: {mobile}")
        
        # 构建短信内容
        sms_content = f"您好，您的求职简历已匹配到合适岗位，请登录就业系统查看详情。"
        
        # 发送短信
        result = send_sms(mobile, sms_content)
        
        if result["success"]:
            return f"<div style='color:green'>匹配结果通知已发送至 {mobile}</div>"
        else:
            return f"<div style='color:red'>发送失败: {result['message']}</div>"
    except Exception as e:
        print(f"发送通知时出错: {str(e)}")
        return f"<div style='color:red'>发送通知时出错: {str(e)}</div>"

# 批量发送匹配结果通知
def batch_send_notifications(result_file):
    """批量发送匹配结果通知
    
    Args:
        result_file: 匹配结果文件路径
    
    Returns:
        str: 包含发送统计信息的HTML
    """
    progress = gr.Progress()
    
    # 加载匹配结果文件
    try:
        progress(0.1, desc="读取匹配结果...")
        with open(result_file.name, 'r', encoding='utf-8') as f:
            match_results = json.load(f)
    except Exception as e:
        return f"<div style='color:red'>读取匹配结果文件失败: {str(e)}</div>"
    
    total = len(match_results)
    success_count = 0
    failed_count = 0
    failed_students = []
    
    progress(0.2, desc="准备发送通知...")
    
    # 遍历每个学生的匹配结果发送通知
    for i, student in enumerate(match_results):
        progress(0.2 + 0.7 * (i/total), desc=f"正在发送 ({i+1}/{total})...")
        student_name = student.get('name', '未知学生')
        student_id = student.get('stu_id', '')
        mobile = student.get('mobile', '')
        if not mobile:
            mobile = get_student_mobile(student_id)
        
        if not mobile:
            failed_count += 1
            failed_students.append({"name": student_name, "id": student_id, "error": "未找到手机号"})
            continue
        
        # 获取学生的匹配结果
        if student.get('matched_jobs'):
            top_jobs = student['matched_jobs'][:3]  # 取前3个匹配岗位
            current_date = datetime.now().strftime("%Y{}%m{}%d{}".format("年", "月", "日"))
            
            # 构建岗位链接列表
            job_links = []
            for idx, job in enumerate(top_jobs, 1):
                job_url = job.get('job_url', '').replace('\\', '/')
                job_links.append(f"岗位{idx}：{job_url}" if job_url else f"岗位{idx}：暂无链接")
            
            # 构建短信内容
            sms_content = f"""亲爱的毕业生同学：
 您好！为帮助大家提高应聘成功率，精准瞄准应聘岗位，学校根据同学们在就业信息网填写的简历，与企业岗位需求进行精准匹配，已为您筛选出{len(top_jobs)}个适配度高的岗位。点击下方链接，即可查看岗位详情：
{chr(10).join(job_links)}

这些推荐岗位会随您简历完善、内容更新及新岗位发布而变化。建议您定期查收短信或关注学校就业信息网、“深技大就业”公众号、学院通知等相关通知，以免错过合适机会。

深圳技术大学学生就业指导中心
{current_date}"""

            # 发送短信
            result = send_sms(mobile, sms_content)
            
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1
                failed_students.append({"name": student_name, "id": student_id, "error": result["message"]})
        else:
            failed_count += 1
            failed_students.append({"name": student_name, "id": student_id, "error": "无匹配结果"})
    
    progress(1.0, desc="发送完成！")
    
    # 生成发送报告
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 20px auto;">
        <h3 style="color: #003788;">短信通知发送报告</h3>
        <div style="background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; 
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <p><strong>总计:</strong> {total}条</p>
            <p><strong>成功:</strong> <span style="color:green">{success_count}条</span></p>
            <p><strong>失败:</strong> <span style="color:red">{failed_count}条</span></p>
        </div>
    """
    
    if failed_students:
        html += """
        <div style="background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; 
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h4 style="color: #e74c3c;">发送失败列表</h4>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead>
                    <tr style="background-color: #f2f6fc;">
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">姓名</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">学号</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">错误信息</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for student in failed_students:
            html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{student['name']}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{student['id']}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{student['error']}</td>
                </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
    
    # 添加弹窗脚本
    html += f"""
    </div>
    <script>
        // 使用模板字符串传递统计信息
        const msg = `批量发送完成！\\n成功：{success_count}条 | 失败：{failed_count}条`;
        
        // 成功时显示绿色弹窗
        {"alert(`${msg}`);" if success_count > 0 else ""}
        
        // 失败时显示红色提示
        {"alert(`${msg}`);" if failed_count > 0 else ""}
    </script>
    """

    html += "</div>"
    return html

# 批量结果展示HTML生成
def build_batch_results_html(results):
    html = """<div style="font-family: 'Segoe UI', sans-serif; max-width: 90%; margin: 20px auto;">
    <h2 style="text-align: center; color: #003788;">批量匹配结果摘要</h2>
    <p style="text-align: center; color: #666;">已为 {student_count} 名学生匹配岗位，每人提供 {job_count} 个岗位推荐</p>
    """.format(student_count=len(results), job_count=len(results[0]["matched_jobs"]) if results else 0)
    
    for student in results:
        html += f"""
        <div style="background: white; border-radius: 10px; padding: 20px; margin-bottom: 30px; 
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h3 style="margin-bottom: 10px; color: #003788;">{student['name']} <span style="color: #666; font-size: 0.8em;">({student['stu_id']})</span></h3>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                    <thead>
                        <tr style="background-color: #f2f6fc;">
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">排名</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">公司</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">匹配度</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">链接</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for i, job in enumerate(student['matched_jobs']):
            match_score = int(job['score'])
            html += f"""
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">#{i+1}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">{job['company_name']}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">
                        <div style="background: {get_score_color(match_score)}; 
                                  display: inline-block; padding: 5px 10px; border-radius: 12px; 
                                  color: white; font-weight: bold;">
                            {match_score}%
                        </div>
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #eee;">
                        <a href="{job['job_url']}" target="_blank" 
                           style="text-decoration: none; color: #0068ca;">查看详情</a>
                    </td>
                </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
        </div>
        """
    
    html += """</div>"""
    return html

def get_score_color(score):
    if score >= 80: return "#27ae60"
    elif score >= 60: return "#f1c40f"
    else: return "#e74c3c"

# 个人匹配处理
def single_match_process(resume_file, job_file=None, min_salary=0, major_filter='不限'):
    if last_update_time:
        print(f"当前使用数据更新时间：{last_update_time}")
    
    # 初始化进度条
    progress = gr.Progress()
    
    # 解析简历
    progress(0.1, desc="解析简历...")
    try:
        # 检查是否有简历文件
        if resume_file is None:
            return "请先上传简历或填写简历表单", None
        
        print(f"处理简历文件: {resume_file}, 类型: {type(resume_file)}")
            
        # 检查是否是表单生成的文件路径
        student_id = ""
        if isinstance(resume_file, str):
            with open(resume_file, 'r', encoding='utf-8') as f:
                resume_data = json.load(f)
                student_id = resume_data.get('index', '')
        else:
            with open(resume_file.name, 'r', encoding='utf-8') as f:
                resume_data = json.load(f)
                student_id = resume_data.get('index', '')
        # 如果是简历集合，取第一个学生的简历
        if isinstance(resume_data, list) and len(resume_data) > 0:
            resume = resume_data[0]
        else:
            resume = resume_data
    except Exception as e:
        return f"简历文件解析失败: {str(e)}"
    
    # 加载企业数据
    progress(0.3, desc="加载企业数据...")
    global job_data
    if job_file:
        try:
            with open(job_file.name, 'r', encoding='utf-8') as f:
                job_data = json.load(f)
        except Exception as e:
            return f"岗位文件解析失败: {str(e)}"
    
    if not job_data:
        return "缺少岗位数据，请上传岗位文件或点击更新数据按钮"
    
    # 应用筛选
    progress(0.5, desc="应用筛选条件...")
    filtered_jobs = []
    
    for job in job_data['jobs']:
        # 获取薪资并解析
        min_k, max_k = parse_salary(job.get('salary', ''))
        
        # 应用薪资筛选条件 (确保转为整数比较)
        try:
            if int(min_k) < int(min_salary):
                continue
        except (TypeError, ValueError):
            # 如果解析失败，跳过薪资筛选
            pass
        
        # 应用专业筛选条件
        if major_filter != "不限":
            # 获取岗位专业字段
            job_major = job.get('major', '')
            # 如果岗位没有指定专业或专业不匹配，则跳过
            if not job_major or major_filter not in job_major:
                continue
        
        filtered_jobs.append(job)
    
    # 如果没有符合条件的岗位
    if not filtered_jobs:
        return "没有找到符合筛选条件的岗位，请调整薪资或专业要求后重试"
    
    # 执行匹配
    results = []
    total = len(filtered_jobs)
    for idx, job in enumerate(filtered_jobs):
        progress(0.6 + 0.3*(idx/total), desc=f"分析岗位 {idx+1}/{total}...")
        job_requirements = job.get('job_requirements', '')
        job_responsibilities = job.get('job_responsibilities', '')
        
        match = get_matching_score(
            resume.get('resume_content', ''), 
            f"{job_responsibilities}\n{job_requirements}"
        )
        
        # 确保match包含score和matches字段
        if not isinstance(match, dict) or 'score' not in match:
            match = {"score": 0, "matches": []}
        
        # 添加更多的错误处理
        min_k, max_k = parse_salary(job.get('salary', ''))
        
        results.append({
            "公司": job.get('company_name', ''),
            "岗位": job.get('job_name', ''),
            "匹配度": match['score'],
            "关键点": "<br>".join(match.get('matches', [])[:3]),
            "薪资": f"{min_k}K-{max_k}K" if min_k and max_k else "未知",
            "链接": job.get('job_url', '')
        })
    
    # 完成进度条
    progress(1.0, desc="完成分析！")
    
    # 确保基于匹配度而非distance进行排序
    sorted_results = sorted(results, key=lambda x: x['匹配度'])
    
    # 只返回前3个最佳匹配
    return build_html_result(sorted_results[:3]),student_id

# 结果展示HTML生成
def build_html_result(results):
    html = """<div style="font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 20px auto;">"""
    for item in results:
        html += f"""
        <div style="background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; 
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: transform 0.2s;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 style="margin:0; color: #003788;">{item['公司']}</h3>
                    <p style="margin:5px 0; color: #0068ca;">{item['岗位']}</p>
                </div>
                <div style="background: {get_score_color(item['匹配度'])}; 
                           width: 60px; height: 60px; border-radius: 50%; 
                           display: flex; align-items: center; justify-content: center;">
                    <span style="color: white; font-weight: bold; font-size: 18px;">{item['匹配度']}</span>
                </div>
            </div>
            <div style="margin-top: 15px;">
                <p style="color: #223259; margin: 8px 0;">薪资：{item['薪资']}</p>
                <p style="color: #223259; margin: 8px 0;">关键匹配：{item['关键点']}</p>
                <a href="{item['链接']}" target="_blank" 
                   style="display: inline-block; padding: 8px 20px; 
                          background: #3498db; color: white; border-radius: 5px; 
                          text-decoration: none; margin-top: 10px;">
                    查看详情 →
                </a>
            </div>
        </div>"""
    return html + "</div>"

def get_resume_optimization(resume_file, form_file, progress=gr.Progress()):
    progress(0.1, desc="正在解析简历内容...")
    try:
        # 获取简历内容
        content = get_resume_content(resume_file, form_file)
        if isinstance(content, dict):  # 处理直接传入的简历数据
            content = content.get('resume_content', '')
        
        progress(0.3, desc="正在调用大模型分析...")
        # 调用大模型获取建议
        feedback = get_resume_feedback(content)
        
        progress(0.8, desc="正在格式化结果...")
        # 转换为HTML
        html = format_feedback_html(feedback)
        
        progress(1.0)
        return html
    except Exception as e:
        print(f"优化建议生成失败: {str(e)}")
        return f"<div style='color:red'>生成失败：{str(e)}</div>"

# 添加数据库查看功能
def list_database_content():
    """列出数据库内容"""
    html = """
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 100%; margin: 20px auto;">
        <h3 style="color: #003788;">数据库内容概览</h3>
    """
    
    # 1. 检查简历向量数据库
    try:
        from resume_chromadb_operater import collection as resume_collection
        resume_count = len(resume_collection.get()["ids"])
        html += f"""
        <div style="background: white; border-radius: 10px; padding: 15px; margin-bottom: 15px; 
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <h4 style="margin-top: 0; color: #003788;">简历数据库</h4>
            <p>存储位置: <code>./chroma_resume_data</code></p>
            <p>简历总数: <strong>{resume_count}</strong></p>
        </div>
        """
    except Exception as e:
        html += f"""
        <div style="background: white; border-radius: 10px; padding: 15px; margin-bottom: 15px; 
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <h4 style="margin-top: 0; color: #003788;">简历数据库</h4>
            <p>状态: <span style="color: red;">无法访问 ({str(e)})</span></p>
        </div>
        """
    
    # 2. 检查岗位向量数据库
    try:
        from job_chromadb_operater import collection as job_collection
        job_count = len(job_collection.get()["ids"])
        html += f"""
        <div style="background: white; border-radius: 10px; padding: 15px; margin-bottom: 15px; 
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <h4 style="margin-top: 0; color: #003788;">岗位数据库</h4>
            <p>存储位置: <code>./chroma_data</code></p>
            <p>岗位总数: <strong>{job_count}</strong></p>
        </div>
        """
    except Exception as e:
        html += f"""
        <div style="background: white; border-radius: 10px; padding: 15px; margin-bottom: 15px; 
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <h4 style="margin-top: 0; color: #003788;">岗位数据库</h4>
            <p>状态: <span style="color: red;">无法访问 ({str(e)})</span></p>
        </div>
        """
    
    # 3. 检查匹配结果文件
    match_files = []
    for file in os.listdir():
        if file.startswith("match_result_") and file.endswith(".json"):
            try:
                # 获取文件信息
                mtime = os.path.getmtime(file)
                size = os.path.getsize(file) / 1024  # 转换为KB
                
                # 读取文件内容获取学生数量
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    student_count = len(data)
                
                match_files.append({
                    "filename": file,
                    "mtime": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "size": f"{size:.1f}KB",
                    "student_count": student_count
                })
            except Exception as e:
                print(f"处理文件 {file} 时出错: {str(e)}")
    
    html += f"""
    <div style="background: white; border-radius: 10px; padding: 15px; margin-bottom: 15px; 
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
        <h4 style="margin-top: 0; color: #003788;">匹配结果文件</h4>
        <p>匹配结果文件总数: <strong>{len(match_files)}</strong></p>
    """
    
    if match_files:
        html += """
        <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
            <thead>
                <tr style="background-color: #f2f6fc;">
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">文件名</th>
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">创建时间</th>
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">文件大小</th>
                    <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">学生数量</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for file in sorted(match_files, key=lambda x: x["mtime"], reverse=True):
            html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{file['filename']}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{file['mtime']}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{file['size']}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{file['student_count']}</td>
                </tr>
            """
        
        html += """
            </tbody>
        </table>
        """
    
    html += """
    </div>
    </div>
    """
    return html

# 查看简历数据库内容
def list_resume_database():
    try:
        from resume_chromadb_operater import collection as resume_collection
        results = resume_collection.get(include=["metadatas"])
        
        html = """
        <div style="font-family: 'Segoe UI', sans-serif; max-width: 100%; margin: 20px auto;">
            <h3 style="color: #003788;">简历数据库内容</h3>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead>
                    <tr style="background-color: #f2f6fc;">
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">ID</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">学号</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">姓名</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for i, (id, metadata) in enumerate(zip(results["ids"], results["metadatas"])):
            student_id = metadata.get("student_id", "未知")
            name = metadata.get("name", "未知")
            
            html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{id}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{student_id}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{name}</td>
                </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        return html
    except Exception as e:
        return f"无法访问简历数据库: {str(e)}"

# 查看岗位数据库内容
def list_job_database():
    try:
        from job_chromadb_operater import collection as job_collection
        results = job_collection.get(include=["metadatas"])
        
        html = """
        <div style="font-family: 'Segoe UI', sans-serif; max-width: 100%; margin: 20px auto;">
            <h3 style="color: #003788;">岗位数据库内容</h3>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead>
                    <tr style="background-color: #f2f6fc;">
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">ID</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">公司名称</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">岗位名称</th>
                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">薪资</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for i, (id, metadata) in enumerate(zip(results["ids"], results["metadatas"])):
            company = metadata.get("company_name", "未知")
            job_name = metadata.get("job_name", "未知")
            salary = metadata.get("salary", "未知")
            
            html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{id}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{company}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{job_name}</td>
                    <td style="padding: 10px; border-bottom: 1px solid #eee;">{salary}</td>
                </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        return html
    except Exception as e:
        return f"无法访问岗位数据库: {str(e)}"
# 界面设计
with gr.Blocks(theme=gr.themes.Base(), title="润小职Agent") as demo:
    with gr.Row(equal_height=True):
        logo_img=gr.Image('sztu.png', interactive=False, label='logo', height=100, width=100,)
        gr.Markdown("""<h1 style="text-align: center; color: #003788; font-size: 3em;">润小职</h1>""")
    
    with gr.Tabs():
        # 个人匹配页面
        with gr.Tab("个人匹配"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 第一步：提供简历信息")
                    # 添加简历表单/上传选项卡
                    with gr.Tabs():
                        with gr.Tab("填写简历"):
                            with gr.Accordion("简历信息", open=False):
                                name_input = gr.Textbox(label="姓名")
                                resume_student_id_input = gr.Textbox(label="学号")
                                mobile_input = gr.Textbox(label="手机号")
                                education_input = gr.Textbox(label="教育背景", placeholder="例如：深圳技术大学，本科，2020-2024")
                                major_input = gr.Textbox(label="专业", placeholder="例如：计算机科学与技术")
                                skills_input = gr.Textbox(label="技能", placeholder="例如：Python, Java, 数据分析...", lines=3)
                                projects_input = gr.Textbox(label="项目经历", placeholder="描述您参与的项目...", lines=5)
                                internships_input = gr.Textbox(label="实习经历", placeholder="描述您的实习经历...", lines=5)

                            submit_form_btn = gr.Button("保存简历信息", variant="primary")
                            form_status = gr.Textbox(label="提交状态", interactive=False)
                            form_file = gr.Textbox(label="生成的文件", visible=False)

                        with gr.Tab("上传简历"):
                            resume_upload = gr.File(label="上传简历（JSON）", file_types=[".json"])
                    
                    company_upload = gr.File(label="上传企业数据（JSON）", file_types=[".json"])
                    
                    current_student_id = gr.State("")
                    
                    with gr.Row():
                        update_status = gr.Textbox(
                            label="数据状态",
                            value="尚未更新",
                            interactive=False,
                            visible=False
                        )
                    manual_update_btn = gr.Button("更新数据", variant="secondary")
                    
                    gr.Markdown("### 第二步：设置条件")
                    with gr.Accordion("筛选设置", open=False):
                        min_salary = gr.Slider(0, 20, 0, label="最低薪资(K/月)")
                        major_filter = gr.Dropdown(["不限", "计算机", "电子", "机械", "自动化"], label="专业要求", value="不限")
                    
                    start_btn = gr.Button("开始智能匹配", variant="primary")
                    
                
                with gr.Column(scale=2):
                    gr.Markdown("### 实时匹配结果")
                    result_html = gr.HTML(label="匹配结果")

                    match_progress = gr.HTML(visible=True)

                    gr.Markdown("### 简历优化建议")
                    feedback_html = gr.HTML(label="优化建议")

                    optimize_progress = gr.HTML(visible=True)
                    
                    feedback_html = gr.HTML(label="优化建议", visible=True) 

                    gr.Markdown("### 🛠 操作面板")
                    with gr.Row():
                        save_btn = gr.Button("保存结果", variant="secondary")
                        send_notification_btn = gr.Button("发送通知", variant="secondary")
                        optimize_btn = gr.Button("生成优化建议", variant="secondary")

                    # 添加短信发送结果显示区域
                    sms_result = gr.HTML(label="短信发送结果", visible=True)
        
        # 批量匹配页面
        with gr.Tab("批量匹配（就业中心）"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 批量上传资料")
                    batch_resume_upload = gr.File(label="上传简历集合（JSON）", file_types=[".json"])
                    batch_job_upload = gr.File(label="上传企业数据（JSON，可选）", file_types=[".json"])
                    
                    gr.Markdown("### 匹配设置")
                    top_n = gr.Slider(1, 10, 3, step=1, label="为每个学生匹配岗位数量")
                    
                    batch_update_btn = gr.Button("更新岗位数据", variant="secondary")
                    with gr.Row():
                        batch_update_status = gr.Textbox(
                            label="数据状态",
                            value="尚未更新",
                            interactive=False,
                            visible=False
                        )
                    
                    batch_start_btn = gr.Button("开始批量匹配", variant="primary")
                
                with gr.Column(scale=2):
                    gr.Markdown("### 批量匹配结果")
                    batch_result_html = gr.HTML(label="批量匹配结果")
                    
                    gr.Markdown("### 下载匹配结果")
                    result_file = gr.File(label="匹配结果JSON文件", interactive=False)
                    
                    gr.Markdown("### 🛠 操作面板")
                    with gr.Row():
                        batch_export_btn = gr.Button("导出Excel", variant="secondary")
                        batch_email_btn = gr.Button("批量发送短信", variant="secondary")

                    # 添加批量短信发送结果显示区域  
                    batch_sms_result = gr.HTML(
    label="批量短信发送结果",
    visible=False,
    elem_id="batch_sms_result"  # 添加ID便于定位
)

    # 个人匹配事件绑定
    submit_form_btn.click(
        fn=process_resume_form,
        inputs=[name_input, resume_student_id_input, mobile_input, education_input, major_input, skills_input, projects_input, internships_input],
        outputs=[form_status, form_file]
    )

    start_btn.click(
        fn=lambda: [gr.update(visible=False), gr.update(visible=True)],  # 隐藏优化建议，显示进度条
        outputs=[feedback_html, match_progress],
        queue=False
    ).then(
        fn=lambda resume_file, form_file, company_file, min_sal, major_fil: 
            single_match_process(
                form_file if form_file else resume_file, 
                company_file, 
                min_sal, 
                major_fil
            ),
        inputs=[resume_upload, form_file, company_upload, min_salary, major_filter],
        outputs=[result_html, current_student_id]     
    ).then(
        fn=lambda: [gr.update(visible=True), gr.update(visible=False)],  # 恢复显示
        outputs=[feedback_html, match_progress],
        queue=False
    )

    manual_update_btn.click(
        fn=manual_update,
        outputs=update_status
    )
    # 添加发送通知按钮事件绑定
    send_notification_btn.click(
        fn=send_match_notification,
        inputs=[resume_student_id_input, current_student_id],
        outputs=sms_result
    ).then(
        fn=lambda: gr.update(visible=True),
        outputs=sms_result
    )
    # 批量匹配事件绑定
    batch_start_btn.click(
        fn=batch_match_process,
        inputs=[batch_resume_upload, batch_job_upload, top_n],
        outputs=[batch_result_html, result_file]
    )
    batch_update_btn.click(
        fn=manual_update,
        outputs=batch_update_status
    )
    # 添加批量发送邮件按钮事件绑定
    batch_email_btn.click(
        fn=batch_send_notifications,
        inputs=[result_file],
        outputs=batch_sms_result
    )

    optimize_btn.click(
        fn=lambda: [gr.update(visible=False), gr.update(visible=True)],  # 隐藏匹配结果，显示进度条
        outputs=[result_html, optimize_progress],
        queue=False
    ).then(
        fn=get_resume_optimization,
        inputs=[resume_upload, form_file],
        outputs=feedback_html,
    ).then(
        fn=lambda: [gr.update(visible=True), gr.update(visible=False)],  # 恢复显示
        outputs=[result_html, optimize_progress],
        queue=False
    )

match_progress = gr.HTML("""
<div style="text-align:center; padding:20px;">
    <div class="loader"></div>
    <p style="color:#666;">正在匹配岗位，请稍候...</p>
</div>
<style>
.loader {
    border: 5px solid #f3f3f3;
    border-radius: 50%;
    border-top: 5px solid #3498db;
    width: 50px;
    height: 50px;
    animation: spin 1s linear infinite;
    margin: 0 auto;
}
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>
""", visible=False)

optimize_progress = gr.HTML("""
<div style="text-align:center; padding:20px;">
    <div class="loader"></div>
    <p style="color:#666;">正在生成优化建议，请稍候...</p>
</div>
<style>
.loader {
    border: 5px solid #f3f3f3;
    border-radius: 50%;
    border-top: 5px solid #27ae60;
    width: 50px;
    height: 50px;
    animation: spin 1s linear infinite;
    margin: 0 auto;
}
</style>
""", visible=False)
# 初始化数据
fetch_data()
# 启动应用
demo.launch(server_port=7860, share=True)
