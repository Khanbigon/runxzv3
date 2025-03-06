import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
from urllib.parse import urljoin
import logging
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class JobCrawler:
    def __init__(self, headless=False):
        self.base_url = "https://sztu.bysjy.com.cn"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }
        self.job_data = []
        self.setup_driver(headless)

    def setup_driver(self, headless=False):
        """设置Selenium WebDriver"""
        try:
            # 创建Edge选项
            options = Options()
            if headless:
                options.add_argument('--headless')  # 无头模式
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f'user-agent={self.headers["User-Agent"]}')
            
            # 初始化Edge浏览器
            service = Service()
            self.driver = webdriver.Edge(service=service, options=options)
            # 设置窗口大小
            self.driver.set_window_size(1920, 1080)
            logging.info(f"Edge WebDriver初始化成功，{'开启' if headless else '未开启'}无头模式")
            
        except Exception as e:
            logging.error(f"WebDriver初始化失败: {e}")
            raise

    def get_job_info(self, url):
        try:
            if "detail/job" not in url:  # 只有在不是职位详情页时才重新加载页面
                logging.info(f"正在获取页面: {url}")
                self.driver.get(url)
                time.sleep(2)  # 减少等待时间
            
            # 添加调试信息
            logging.info(f"页面标题: {self.driver.title}")
            
            # 等待表格加载
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "jobfair-grid"))
                )
                logging.info("表格元素加载成功")
            except Exception as e:
                logging.warning(f"等待表格加载超时: {e}")
            
            # 获取页面内容
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'lxml')
            
            # 查找所有职位行
            job_rows = soup.find_all('tr', attrs={'data-company': True})
            logging.info(f"找到 {len(job_rows)} 行职位信息")
            
            if len(job_rows) == 0:
                logging.warning("未找到职位信息，可能是页面结构不匹配或者暂无数据")
                return False
            
            # 保存所有职位的链接和信息，然后一次性处理
            job_info_list = []
            
            # 处理每个职位行
            for row in job_rows:
                # 获取该行中的所有职位链接和名称
                job_links = row.find_all('a', href=lambda x: x and '/detail/job?id=' in x)
                
                # 处理每个职位
                for job_link in job_links:
                    position = job_link.text.strip()
                    job_detail_url = urljoin(self.base_url, job_link['href'])
                    
                    # 获取专业要求（在职位链接的父元素的下一个兄弟元素中）
                    major_cell = job_link.find_parent('div').find_parent('td').find_next_sibling('td')
                    major = major_cell.get_text(strip=True) if major_cell else "未知专业"
                    
                    job_info_list.append((position, job_detail_url, major))
            
            # 保存当前列表页URL，以便后续返回
            current_list_url = self.driver.current_url
            
            # 依次访问每个职位详情页
            for position, job_detail_url, major in job_info_list:
                logging.info(f"正在获取职位详情: {position}, {major}")
                # 获取职位详情
                job_details = self.get_job_details(job_detail_url, position, major)
                if job_details:
                    self.job_data.append(job_details)
                time.sleep(1)  # 保持1秒间隔，避免请求过快
                
                # 每次获取完职位详情后，返回到列表页
                self.driver.get(current_list_url)
                time.sleep(2)  # 等待列表页面加载
            
            return True
        except Exception as e:
            logging.error(f"获取职位信息时发生错误: {e}")
            return False

    def get_job_details(self, url, position, major):
        try:
            logging.info(f"正在获取职位详情: {url}")
            self.driver.get(url)
            
            # 等待页面主要内容加载
            try:
                # 等待公司名称元素出现
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "company-name"))
                )
                # 等待职位描述模块出现
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "detail-module"))
                )
                time.sleep(2)  # 额外等待确保内容完全加载
                logging.info("职位详情加载成功")
            except Exception as e:
                logging.warning(f"等待职位详情加载超时: {e}")
                return None

            # 使用JavaScript获取所有职位详情信息
            job_details = self.driver.execute_script("""
                function getCleanText(element) {
                    return element ? element.textContent.trim() : '';
                }

                function extractContentBetweenLabels(startLabel, endLabels) {
                    // 获取所有职位描述内容
                    const detailModule = document.querySelector('.detail-module .dm-cont');
                    if (!detailModule) return '';
                    
                    // 获取整个HTML内容
                    let html = detailModule.innerHTML;
                    
                    // 查找开始标签的位置
                    let startIdx = html.indexOf(startLabel);
                    if (startIdx === -1) return '';
                    
                    // 从开始标签后开始查找
                    startIdx += startLabel.length;
                    
                    // 查找最近的结束标签位置
                    let endIdx = html.length;
                    for (const endLabel of endLabels) {
                        const pos = html.indexOf(endLabel, startIdx);
                        if (pos !== -1 && pos < endIdx) {
                            endIdx = pos;
                        }
                    }
                    
                    // 提取内容
                    let content = html.substring(startIdx, endIdx).trim();
                    
                    // 清理内容，移除多余的HTML标签
                    // 创建临时DOM元素解析HTML
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = content;
                    
                    // 移除所有空的p.dm-text标签
                    tempDiv.querySelectorAll('p.dm-text').forEach(p => {
                        if (!p.textContent.trim()) {
                            p.remove();
                        }
                    });
                    
                    // 获取所有的实际内容段落
                    const paragraphs = tempDiv.querySelectorAll('p');
                    const textContents = [];
                    
                    paragraphs.forEach(p => {
                        // 忽略空段落
                        if (p.textContent.trim()) {
                            textContents.push(p.textContent.trim());
                        }
                    });
                    
                    // 返回纯文本内容，用换行符分隔各段落
                    return textContents.join('\\n');
                }
                
                // 1. 获取公司名称和职位名称
                let companyName = getCleanText(document.querySelector('.details-head h1.dh-tit p.company-name'));
                let jobName = getCleanText(document.querySelector('.details-head h1.dh-tit p.job-name'));
                
                // 2. 获取基本信息
                let salary = '';
                let location = '';
                let education = '';
                let welfare = '';
                
                // 获取薪资
                let salaryElement = document.querySelector('.tag-list .pub-orange-text');
                if (salaryElement) {
                    salary = salaryElement.textContent.trim();
                }
                
                // 获取标签信息
                document.querySelectorAll('.tag-list .tag-item').forEach(tag => {
                    let text = tag.textContent.trim();
                    if (text.includes('省') || text.includes('市')) {
                        location = text;
                    } else if (text.includes('本科') || text.includes('专科') || text.includes('学历')) {
                        education = text;
                    }
                });
                
                // 获取福利标签
                let welfareElems = document.querySelectorAll('.job-welfare');
                welfare = Array.from(welfareElems).map(elem => elem.textContent.trim()).join(' ');
                
                // 可能的结束标签
                const endLabels = ['<p class="dm-text">岗位要求：</p>', '<p class="dm-text">投递说明：</p>', '<p class="dm-text">其他描述：</p>'];
                
                // 3. 获取职位描述信息
                let responsibilities = extractContentBetweenLabels('<p class="dm-text">岗位职责：</p>', endLabels);
                let requirements = extractContentBetweenLabels('<p class="dm-text">岗位要求：</p>', 
                    ['<p class="dm-text">投递说明：</p>', '<p class="dm-text">其他描述：</p>']);
                let applicationInfo = extractContentBetweenLabels('<p class="dm-text">投递说明：</p>', 
                    ['<p class="dm-text">其他描述：</p>']);
                let otherInfo = extractContentBetweenLabels('<p class="dm-text">其他描述：</p>', []);
                
                return {
                    company_name: companyName || '未知公司',
                    job_name: jobName || '未知职位',
                    salary: salary,
                    location: location,
                    education: education,
                    welfare: welfare,
                    job_responsibilities: responsibilities,
                    job_requirements: requirements,
                    application_info: applicationInfo,
                    other_info: otherInfo
                };
            """)
            
            if job_details:
                # 从URL中提取job_id
                job_id = None
                try:
                    # 解析URL中的id参数
                    import re
                    # 使用正则表达式匹配id=数字部分
                    match = re.search(r'id=(\d+)', url)
                    if match:
                        job_id = match.group(1)
                except Exception as e:
                    logging.error(f"提取job_id时发生错误: {e}")
                
                # 添加固定信息
                job_details.update({
                    'position': position,
                    'major': major,
                    'job_url': url,
                    'job_id': job_id  # 添加提取的job_id
                })
                logging.info(f"成功获取公司名称: {job_details['company_name']}, job_id: {job_id}")
                return job_details
            else:
                logging.error("获取职位详情失败")
                return None
                
        except Exception as e:
            logging.error(f"获取职位详情时发生错误: {e}")
            return None

    def get_total_pages(self):
        try:
            # 等待分页元素加载
            pagination = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "paginationjs"))
            )
            logging.info("分页元素加载成功")
            
            # 获取总页数
            page_info = self.driver.find_element(By.CLASS_NAME, "paginationjs-go-button").text
            # 提取类似 "1/35 共514条记录" 中的 35
            if '/' in page_info:
                total_pages = int(page_info.split('/')[1].split()[0].strip())
                logging.info(f"总页数: {total_pages}")
                return total_pages
            else:
                logging.warning("未找到预期的页码格式，返回默认值1")
                return 1
            
        except Exception as e:
            logging.error(f"获取总页数时发生错误: {e}")
            return 1

    def go_to_page(self, page):
        try:
            # 等待输入框和跳转按钮加载
            input_box = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "J-paginationjs-go-pagenumber"))
            )
            go_button = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "J-paginationjs-go-button"))
            )
            
            # 清空输入框
            input_box.clear()
            # 输入页码
            input_box.send_keys(str(page))
            time.sleep(1)
            
            # 点击跳转按钮
            go_button.click()
            logging.info(f"已点击跳转到第 {page} 页")
            
            # 等待新数据加载
            time.sleep(5)
            
            # 检查表格是否有新数据
            try:
                table = WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "jobfair-grid"))
                )
                rows = table.find_elements(By.TAG_NAME, "tr")
                if len(rows) > 1:  # 表头也算一行，所以要大于1
                    logging.info(f"成功加载第 {page} 页数据，找到 {len(rows)-1} 行数据")
                    return True
                else:
                    logging.error(f"表格数据为空")
                    return False
            except Exception as e:
                logging.error(f"等待表格数据加载失败: {e}")
                return False
                
        except Exception as e:
            logging.error(f"跳转到第 {page} 页失败: {e}")
            return False

    def crawl(self, job_fair_id, max_pages=None):
        try:
            base_url = f"https://sztu.bysjy.com.cn/detail/jobfair?id={job_fair_id}"
            logging.info(f"开始爬取招聘会页面: {base_url}")
            
            self.driver.get(base_url)
            time.sleep(2)  # 等待初始页面加载
            
            # 获取总页数
            total_pages = self.get_total_pages()
            logging.info(f"检测到总页数: {total_pages}")
            
            # 如果设置了最大页数限制，则使用较小的值
            if max_pages and max_pages < total_pages:
                total_pages = max_pages
                logging.info(f"根据设置，将只爬取前 {max_pages} 页")
            
            # 爬取所有页面
            for page in range(1, total_pages + 1):
                logging.info(f"正在爬取第{page}页，共{total_pages}页")
                
                # 如果不是第一页，需要跳转到指定页面
                if page > 1:
                    if not self.go_to_page(page):
                        logging.error(f"跳转到第{page}页失败，跳过此页")
                        continue
                
                # 爬取当前页的职位信息
                if not self.get_job_info(self.driver.current_url):
                    logging.error(f"爬取第{page}页失败")
                
                # 每爬取5页保存一次数据(断点续传功能)
                if page % 5 == 0 or page == total_pages:
                    self.save_data(job_fair_id, is_temp=True)
                    logging.info(f"已完成 {page}/{total_pages} 页的爬取，已保存临时数据")
            
            # 保存最终数据
            self.save_data(job_fair_id)
            
        except Exception as e:
            logging.error(f"爬取过程中发生错误: {e}")
            # 即使出错也尝试保存已爬取的数据
            if self.job_data:
                self.save_data(job_fair_id, is_error=True)
        finally:
            self.driver.quit()
    
    def save_data(self, job_fair_id, is_temp=False, is_error=False):
        """保存数据到JSON文件"""
        if not self.job_data:
            logging.warning("没有数据需要保存")
            return
            
        # 根据不同情况设置文件名
        if is_temp:
            output_file = f'jobfair_{job_fair_id}_temp_data.json'
        elif is_error:
            output_file = f'jobfair_{job_fair_id}_error_data.json'
        else:
            output_file = f'jobfair_{job_fair_id}_data.json'
            
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'job_fair_id': job_fair_id,
                'total_jobs': len(self.job_data),
                'crawl_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'jobs': self.job_data
            }, f, ensure_ascii=False, indent=2)
            
        logging.info(f"数据已保存到 {output_file}")
        logging.info(f"共保存 {len(self.job_data)} 个职位信息")

if __name__ == "__main__":
    try:
        import argparse
        
        # 创建命令行参数解析器
        parser = argparse.ArgumentParser(description='招聘会网站职位信息爬虫')
        parser.add_argument('--id', type=int, default=22339, help='招聘会ID')
        parser.add_argument('--max_pages', type=int, help='最大爬取页数，不设置则爬取全部页面')
        parser.add_argument('--headless', action='store_true', help='是否使用无头模式运行浏览器')
        args = parser.parse_args()
        
        logging.info(f"开始爬取招聘会ID: {args.id}")
        if args.max_pages:
            logging.info(f"设置最大爬取页数: {args.max_pages}")
        if args.headless:
            logging.info("将使用无头模式运行浏览器")
        
        crawler = JobCrawler(headless=args.headless)
        crawler.crawl(args.id, args.max_pages)
        
    except KeyboardInterrupt:
        logging.info("程序被用户中断")
    except Exception as e:
        logging.error(f"程序执行出错: {e}")