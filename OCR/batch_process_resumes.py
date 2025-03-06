import json
from pathlib import Path
from simple_resume_reader import read_resume_image

def process_all_resumes():
    """
    处理resumes文件夹中的所有简历并生成JSON文件
    """
    # 获取resumes目录
    resumes_dir = Path(__file__).parent / 'resumes'
    if not resumes_dir.exists():
        print(f"错误：{resumes_dir} 目录不存在!")
        return

    # 获取所有图片文件
    image_files = set() # 使用集合去重
    for ext in ['*.jpg', '*.JPG', '*.jpeg', '*.JPEG']:
        image_files.update(resumes_dir.glob(ext))
    image_files = list(image_files)  # 转回列表

    if not image_files:
        print("错误：未找到图片文件！")
        print(f"请检查 {resumes_dir} 目录中是否存在jpg/jpeg图片文件")
        return

    # 处理所有简历
    results = []
    total_files = len(image_files)
    
    for i, image_file in enumerate(image_files, 1):
        print(f"正在处理 {i}/{total_files}: {image_file.name}")
        
        name, student_id, content = read_resume_image(image_file)
        
        if name and content:  # 只添加成功处理的结果
            resume_data = {
                "name": name,
                "stu_ids": student_id,
                "resume_content": content
            }
            results.append(resume_data)
        else:
            print(f"警告：无法处理文件 {image_file.name}")

    # 保存结果到JSON文件
    output_file = Path(__file__).parent / 'resume_data.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"\n处理完成！")
    print(f"总共处理了 {total_files} 个文件")
    print(f"成功提取了 {len(results)} 份简历")
    print(f"结果已保存到: {output_file}")

if __name__ == '__main__':
    process_all_resumes()
