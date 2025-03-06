import cv2
import numpy as np
from paddleocr import PaddleOCR
from pathlib import Path

def extract_name_and_id(filename):
    """从文件名中提取姓名和学号"""
    base_name = Path(filename).stem
    try:
        name, student_id = base_name.split('_')
        return name, student_id
    except ValueError:
        return base_name, ""

def preprocess_image(img):
    """图像预处理"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary

def read_resume_image(image_path):
    """
    读取简历图片并返回基本信息
    
    参数:
        image_path: 图片路径字符串或Path对象
    
    返回:
        tuple: (姓名, 学号, 简历内容)
    """
    try:
        # 初始化OCR引擎
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang="ch",
            show_log=False,
            use_gpu=True,
            enable_mkldnn=True,
            cpu_threads=10
        )

        # 转换路径对象
        image_path = Path(image_path)
        
        # 提取姓名和学号
        name, student_id = extract_name_and_id(image_path.name)
        
        # 读取图片
        img = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("无法读取图片!")
            
        # 图片预处理
        binary = preprocess_image(img)
        
        # OCR识别
        result = ocr.ocr(binary, cls=True)
        
        # 提取文本内容
        resume_content = []
        if result and isinstance(result, list) and result[0]:
            for line in result[0]:
                if isinstance(line, (list, tuple)) and len(line) > 1:
                    confidence = line[1][1]
                    text = line[1][0]
                    if confidence > 0.5:  # 只保留置信度>0.5的结果
                        resume_content.append(text)
        
        # 将所有文本组合成一个字符串
        full_content = '\n'.join(resume_content)
        
        return name, student_id, full_content

    except Exception as e:
        print(f"处理图片时出错: {e}")
        return None, None, None

def test_reader():
    """测试函数"""
    # 测试目录中的第一个jpg文件
    resumes_dir = Path(__file__).parent / 'resumes'
    if not resumes_dir.exists():
        print(f"错误：{resumes_dir} 目录不存在!")
        return
    
    jpg_files = set()  # 使用集合去重
    for ext in ['*.jpg', '*.JPG', '*.jpeg', '*.JPEG']:
        jpg_files.update(resumes_dir.glob(ext))
    image_files = list(image_files)  # 转回列表

    if not jpg_files:
        print("错误：未找到jpg文件！")
        return
    
    # 读取第一个文件
    first_file = jpg_files[0]
    print(f"处理文件: {first_file.name}")
    
    name, student_id, content = read_resume_image(first_file)
    
    print(f"\n提取结果:")
    print(f"姓名: {name}")
    print(f"学号: {student_id}")
    print(f"内容长度: {len(content) if content else 0} 字符")
    print("\n内容预览:")
    print(content[:500] + "..." if content and len(content) > 500 else content)

if __name__ == '__main__':
    test_reader()
