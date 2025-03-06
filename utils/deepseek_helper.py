import os
import json
import requests
from dotenv import load_dotenv
#这个类封装的generate_matching_analysis（）方法用于生成简历与职位的匹配分析
#它调用了DeepSeek API，将简历文本和职位信息作为输入，返回一个简历优化建议和技能提升建议的JSON格式结果
class DeepSeekHelper:
    """AI分析助手类，用于生成简历匹配分析"""
    
    def __init__(self):
        """初始化DeepSeekHelper，加载API配置"""
        load_dotenv()
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_BASE_URL")
        
    def _call_api(self, messages):
        """调用DeepSeek API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages
        }
        
        response = requests.post(f"{self.base_url}/v1/chat/completions", 
                               headers=headers, 
                               json=payload)
        
        if response.status_code != 200:
            raise Exception(f"API调用失败: {response.text}")
            
        return response.json()["choices"][0]["message"]["content"]
        
    def generate_matching_analysis(self, resume_text: str, matched_jobs: list) -> dict:
        """生成简历与职位的匹配分析"""
        # 构建提示词
        prompt = f"""
你是AI简历分析助手，请分析以下简历和职位信息，并提供详细的匹配分析：

简历内容：
{resume_text}

职位信息：
{json.dumps(matched_jobs, ensure_ascii=False, indent=2)}

请提供以下格式的JSON分析结果：
1. 对每个职位的匹配度分析（matching_analysis）
2. 简历优化建议（resume_optimization）
3. 技能提升建议（skill_improvement）
"""

        messages = [
            {"role": "system", "content": "你是一个专业的简历分析助手，请提供客观、专业的分析建议,你只能在提供的职位里进行分析，不要输出与分析简历无关的信息。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            # 调用API获取分析结果
            response = self._call_api(messages)
            # 将响应转换为字典格式
            result = json.loads(response)
            return result
        except Exception as e:
            return {
                "error": f"生成分析失败: {str(e)}",
                "matching_analysis": [],
                "resume_optimization": [],
                "skill_improvement": []
            }