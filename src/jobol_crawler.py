import time
import json
import logging
import argparse
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from urllib.parse import urljoin

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class OnlineRecruitmentCrawler:
    def __init__(self, headless=False, disable_debug=False):
        """初始化爬虫，设置Edge浏览器"""
        logging.info("正在初始化在线招聘爬虫...")
        self.disable_debug = disable_debug
        try:
            options = Options()
            if headless:
                options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-infobars')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            logging.info("尝试初始化Edge WebDriver...")
            self.driver = webdriver.Edge(options=options)
            self.driver.set_window_size(1920, 1080)
            logging.info(f"Edge WebDriver初始化成功，{'开启' if headless else '未开启'}无头模式")
            
            # 设置全局超时
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)
            
            # 设置基础URL
            self.base_url = "https://sztu.bysjy.com.cn"
            
            # 初始化数据存储结构
            self.job_data = []
            
        except Exception as e:
            logging.error(f"WebDriver初始化失败: {e}")
            raise
    
    def __del__(self):
        """确保关闭浏览器"""
        try:
            if hasattr(self, 'driver'):
                logging.info("关闭WebDriver...")
                self.driver.quit()
        except Exception as e:
            logging.error(f"关闭WebDriver时出错: {e}")
    
    def get_total_pages(self):
        """获取总页数"""
        try:
            # 等待分页控件出现
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".paginationjs"))
            )
            
            # 获取总页数
            pagination = self.driver.find_element(By.CSS_SELECTOR, ".paginationjs")
            page_items = pagination.find_elements(By.CSS_SELECTOR, ".paginationjs-page")
            
            if page_items:
                # 找出最大页码
                max_page = 1
                for item in page_items:
                    try:
                        page_num = int(item.get_attribute("data-num"))
                        max_page = max(max_page, page_num)
                    except (ValueError, TypeError):
                        continue
                return max_page
            else:
                return 1  # 如果没有分页按钮，则只有一页
        except TimeoutException:
            logging.warning("未找到分页控件，假设只有一页")
            return 1
        except Exception as e:
            logging.error(f"获取总页数时发生错误: {e}")
            return 1
    
    def go_to_page(self, page):
        """跳转到指定页码"""
        try:
            # 如果不是第一页，点击分页控件跳转
            if page > 1:
                logging.info(f"尝试跳转到第 {page} 页")
                
                # 等待分页控件出现
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".paginationjs"))
                )
                
                try:
                    # 尝试通过数据属性找到页码按钮
                    page_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, f".paginationjs-page[data-num='{page}']"))
                    )
                    self.driver.execute_script("arguments[0].click();", page_button)
                    logging.info(f"已点击页码按钮 {page}")
                except (NoSuchElementException, TimeoutException):
                    # 如果找不到特定页码，尝试点击下一页直到达到目标页
                    current_page = 1
                    while current_page < page:
                        try:
                            next_button = WebDriverWait(self.driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, ".paginationjs-next"))
                            )
                            self.driver.execute_script("arguments[0].click();", next_button)
                            current_page += 1
                            time.sleep(2)
                            logging.info(f"已点击下一页，当前页码 {current_page}")
                        except Exception as e:
                            logging.error(f"点击下一页时出错: {e}")
                            break
                
                # 等待页面重新加载
                time.sleep(3)
                    
            return True
        except Exception as e:
            logging.error(f"跳转到第 {page} 页失败: {e}")
            return False
                
    def crawl(self, max_pages=None, output_file="recruitment_data.json"):
        """爬取在线招聘页面的核心方法"""
        try:
            base_url = "https://sztu.bysjy.com.cn/module/onlines"
            logging.info(f"开始爬取在线招聘页面: {base_url}")
            
            try:
                self.driver.get(base_url)
                time.sleep(5)  # 等待初始页面加载
                logging.info(f"页面标题: {self.driver.title}")
            except Exception as e:
                logging.error(f"加载页面出错: {e}")
                return False
            
            # 获取总页数
            total_pages = self.get_total_pages()
            logging.info(f"检测到总页数: {total_pages}")
            
            # 如果设置了最大页数限制，则使用较小的值
            if max_pages and max_pages < total_pages:
                total_pages = max_pages
                logging.info(f"根据设置，将只爬取前 {max_pages} 页")
            
            # 遍历每一页
            for page in range(1, total_pages + 1):
                logging.info(f"正在爬取第{page}页，共{total_pages}页")
                
                # 跳转到指定页面
                if page > 1 and not self.go_to_page(page):
                    continue
                
                # 获取当前页面的所有在线招聘项目
                online_events = self.get_online_events()
                logging.info(f"第{page}页找到{len(online_events)}个招聘会")
                
                for event in online_events:
                    logging.info(f"正在处理在线招聘会: {event['title']}")
                    
                    try:
                        # 点击进入招聘会详情页
                        event_id = event['id']
                        event_url = f"https://sztu.bysjy.com.cn/detail/online?id={event_id}&menu_id="
                        self.driver.get(event_url)
                        time.sleep(3)
                        
                        # 在招聘会详情页获取所有职位信息
                        job_data = self.crawl_online_event_jobs(event)
                        logging.info(f"在招聘会'{event['title']}'中获取了{len(job_data)}个职位")
                        self.job_data.extend(job_data)
                        
                        # 每处理完一个招聘会后保存数据到单个文件
                        self.save_data(output_file, event_id, is_temp=True)
                    except Exception as e:
                        logging.error(f"处理招聘会'{event['title']}'时出错: {e}")
                    
                    # 返回列表页
                    try:
                        self.driver.get(base_url)
                        time.sleep(3)
                        if page > 1:
                            self.go_to_page(page)
                    except Exception as e:
                        logging.error(f"返回列表页出错: {e}")
                        continue
                
                # 每页完成后更新单一JSON文件
                self.save_data(output_file, "all", page_num=page)
                logging.info(f"已完成 {page}/{total_pages} 页的爬取，已更新数据文件")
            
            # 将最终数据保存到单一JSON文件
            if self.job_data:
                self.save_data(output_file, "all")
                return True
            else:
                logging.warning("未获取到任何职位数据")
                return False
                
        except Exception as e:
            logging.error(f"爬取过程中发生错误: {e}")
            
            # 即使出错也尝试保存已爬取的数据
            if self.job_data:
                self.save_data(output_file, "all", is_error=True)
                
            return False
        finally:
            self.driver.quit()
    
    def save_data(self, output_file, job_fair_id, is_temp=False, is_error=False, page_num=None):
        """保存数据到单个JSON文件"""
        if not self.job_data:
            logging.warning("没有数据需要保存")
            return
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"创建输出目录: {output_dir}")
        
        # 读取现有数据（如果文件存在）
        existing_data = {"jobs": [], "total_jobs": 0, "last_updated": ""}
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logging.warning(f"读取现有JSON文件失败: {e}")
                existing_data = {"jobs": []}
        
        # 合并数据到单一文件
        # 检查是否已存在相同job_id的数据，避免重复
        new_job_ids = set(job.get('job_id') for job in self.job_data)
        existing_jobs = []
        
        for job in existing_data.get("jobs", []):
            if job.get('job_id') not in new_job_ids:
                existing_jobs.append(job)
        
        # 合并数据
        all_jobs = existing_jobs + self.job_data
        
        # 更新数据
        data_to_save = {
            'total_jobs': len(all_jobs),
            'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
            'jobs': all_jobs
        }
        
        # 添加状态信息
        if is_temp:
            data_to_save['status'] = "临时数据"
        elif is_error:
            data_to_save['status'] = "错误时保存"
        else:
            data_to_save['status'] = "完整数据"
        
        if page_num:
            data_to_save['last_page_processed'] = page_num
            
        # 保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            
        logging.info(f"数据已更新到 {output_file}")
        logging.info(f"当前共有 {len(all_jobs)} 个职位信息")
    
    def get_online_events(self):
        """获取当前页面上的所有在线招聘会"""
        events = []
        try:
            # 等待页面加载完成
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".item-content"))
            )
            
            logging.info("页面已加载，开始解析在线招聘会列表")
            
            # 直接从页面源码解析招聘项目，而不是使用Selenium查找元素
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 修改：只查找主内容区域内的招聘会链接，而不是整个页面的链接
            # 查找主要内容区域，通常是一个特定的容器
            content_container = soup.select_one('.container .item-list') or \
                               soup.select_one('.list-content') or \
                               soup.select_one('.content-area')
            
            if content_container:
                # 只在主内容区域内查找链接
                event_links = content_container.select("a.item-link")
            else:
                # 如果找不到主内容区域，使用更严格的选择器定位真正的招聘会链接
                # 排除明显的导航菜单链接
                event_links = []
                for link in soup.select("a.item-link"):
                    # 检查是否不是导航链接
                    href = link.get("href", "")
                    if "detail/online?id=" in href or ("/detail/online" in href and "id=" in href):
                        event_links.append(link)
                
                # 如果仍找不到，尝试其他特征来筛选
                if not event_links:
                    event_links = [link for link in soup.select("a.item-link") 
                                   if not any(nav in link.text.lower() for nav in 
                                             ["首页", "概况", "通知", "公告", "动态", "政策", "指导", "服务"])]
            
            logging.info(f"在页面源码中找到 {len(event_links)} 个招聘会链接")
            
            for link in event_links:
                href = link.get("href")
                if href and "id=" in href:
                    # 提取ID，确保是在线招聘而不是其他类型页面
                    if "detail/online" in href or "onlines" in href:
                        event_id = href.split("id=")[1].split("&")[0] if "&" in href else href.split("id=")[1]
                        title = link.get("title") or link.text.strip()
                        
                        events.append({
                            "id": event_id,
                            "title": title,
                            "url": f"https://sztu.bysjy.com.cn{href}" if href.startswith("/") else href
                        })
                        logging.info(f"已提取招聘会: {title} (ID: {event_id})")
                    else:
                        logging.debug(f"忽略非在线招聘链接: {href}")
            
            # 如果使用BeautifulSoup仍然找不到，尝试直接使用Selenium精确查找
            if not events:
                logging.info("尝试使用Selenium精确查找招聘会链接")
                try:
                    # 先查找内容容器限制查找范围
                    container = None
                    for selector in ['.container .item-list', '.list-content', '.content-area']:
                        containers = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if containers:
                            container = containers[0]
                            break
                    
                    # 在容器中查找链接，如果有容器
                    if container:
                        links = container.find_elements(By.CSS_SELECTOR, "a.item-link")
                    else:
                        # 直接查找所有detail/online链接
                        links = self.driver.find_elements(By.CSS_SELECTOR, 
                                                        "a[href*='detail/online?id='], a[href*='/detail/online'][href*='id=']")
                    
                    for link in links:
                        href = link.get_attribute("href")
                        if href and "id=" in href and ("detail/online" in href or "onlines" in href):
                            event_id = href.split("id=")[1].split("&")[0] if "&" in href else href.split("id=")[1]
                            title = link.get_attribute("title") or link.text.strip()
                            
                            # 排除导航链接
                            if not any(nav in title.lower() for nav in ["首页", "概况", "通知", "公告", "动态", "政策", "指导", "服务"]):
                                events.append({
                                    "id": event_id,
                                    "title": title,
                                    "url": href
                                })
                                logging.info(f"使用Selenium找到招聘会: {title} (ID: {event_id})")
                except Exception as e:
                    logging.error(f"使用Selenium查找招聘会链接时出错: {e}")
                
        except Exception as e:
            logging.error(f"获取在线招聘会列表失败: {e}")
        
        return events
    
    def crawl_online_event_jobs(self, event):
        """爬取特定在线招聘会的所有职位信息"""
        job_data = []
        
        try:
            # 增加超时等待，确保页面加载完成
            try:
                # 等待页面上任意一个关键元素出现
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 
                        ".dm-tit, .detail-module, .content-area, button.send-resume, button.pub-btn"))
                )
            except:
                logging.warning("等待页面加载超时")
                
            # 修复：添加新方法直接查找职位项
            job_items = self.driver.find_elements(By.CSS_SELECTOR, ".dm-cont .item, .dm-cont .job-item, .dm-cont div[class*='job']")
            logging.info(f"发现 {len(job_items)} 个职位项")
            
            if job_items:
                # 每个职位项可能包含有名称、查看详情按钮等
                for i, item in enumerate(job_items):
                    try:
                        # 首先尝试获取职位信息
                        job_title = ""
                        try:
                            # 寻找职位名称元素
                            title_elem = item.find_element(By.CSS_SELECTOR, "a.item-link, .job-name, h3, strong")
                            job_title = title_elem.text.strip()
                            logging.info(f"找到职位名称: {job_title}")
                        except:
                            logging.warning(f"无法在职位项 {i+1} 中找到职位名称")
                        
                        # 查找查看详情按钮
                        try:
                            detail_btn = item.find_element(By.CSS_SELECTOR, 
                                                        "button.send-resume, button.pub-btn, a.btn, a[href*='job?id=']")
                            
                            # 获取职位ID
                            job_id = None
                            
                            # 如果是链接，尝试从href获取ID
                            if detail_btn.tag_name == "a":
                                href = detail_btn.get_attribute("href")
                                if href and "job?id=" in href:
                                    job_id = href.split("id=")[1].split("&")[0] if "&" in href else href.split("id=")[1]
                                    logging.info(f"从链接中提取到job_id: {job_id}")
                                    
                                    # 直接访问职位详情页
                                    job_url = href if href.startswith("http") else f"https://sztu.bysjy.com.cn{href}"
                                    self.driver.get(job_url)
                                    time.sleep(3)
                            else:
                                # 如果是按钮，先尝试从data-id属性获取
                                job_id = detail_btn.get_attribute("data-id")
                                logging.info(f"从按钮的data-id属性获取: {job_id}")
                                
                                # 如果获取不到ID，就点击按钮
                                if not job_id:
                                    logging.info("尝试点击详情按钮")
                                    self.driver.execute_script("arguments[0].click();", detail_btn)
                                    time.sleep(3)
                                    
                                    # 检查是否跳转到了详情页
                                    if "detail/job" in self.driver.current_url:
                                        current_url = self.driver.current_url
                                        job_id = current_url.split("id=")[1].split("&")[0] if "&" in current_url else current_url.split("id=")[1]
                                        logging.info(f"点击后跳转到职位页面，提取到job_id: {job_id}")
                                else:
                                    # 如果有ID，构造URL直接访问
                                    job_url = f"https://sztu.bysjy.com.cn/detail/job?id={job_id}"
                                    self.driver.get(job_url)
                                    time.sleep(3)
                            
                            # 如果获取到了job_id，提取职位详情
                            if job_id:
                                # 爬取职位详情
                                job_details = self.get_job_details(job_id)
                                if job_details:
                                    job_details.update({
                                        "event_id": event["id"],
                                        "event_title": event["title"],
                                        "job_id": job_id
                                    })
                                    # 如果之前未能提取到职位名称，使用详情中的名称
                                    if not job_title and job_details.get('job_name'):
                                        job_title = job_details['job_name']
                                    
                                    job_data.append(job_details)
                                    logging.info(f"成功获取职位详情: {job_title or job_details.get('job_name', 'Unknown')}")
                            
                            # 返回招聘会页面继续处理
                            self.driver.get(event['url'])
                            time.sleep(3)
                            
                        except NoSuchElementException:
                            logging.warning(f"在职位项 {i+1} 中未找到详情按钮/链接")
                        except Exception as e:
                            logging.error(f"处理职位项 {i+1} 的详情按钮/链接时出错: {e}")
                    
                    except Exception as e:
                        logging.error(f"处理职位项 {i+1} 时出错: {e}")
            
            # 如果上面的方法没有找到职位，尝试其他方式
            if not job_data:
                logging.info("未通过职位项找到职位，尝试查找职位链接")
                
                # 分析招聘会页面，寻找职位链接
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                job_links = soup.select("a[href*='/detail/job?id='], a[href*='job?id=']")
                
                logging.info(f"找到 {len(job_links)} 个可能的职位链接")
                
                for link in job_links:
                    href = link.get("href")
                    if href and "job?id=" in href:
                        try:
                            job_id = href.split("id=")[1].split("&")[0] if "&" in href else href.split("id=")[1]
                            
                            if job_id:
                                job_url = f"https://sztu.bysjy.com.cn{href}" if href.startswith("/") else href
                                logging.info(f"访问职位链接: {job_url}")
                                
                                self.driver.get(job_url)
                                time.sleep(3)
                                
                                # 爬取职位详情
                                job_details = self.get_job_details(job_id)
                                if job_details:
                                    job_details.update({
                                        "event_id": event["id"],
                                        "event_title": event["title"],
                                        "job_id": job_id,
                                        "job_url": job_url
                                    })
                                    job_data.append(job_details)
                                    logging.info(f"成功获取职位详情: {job_details.get('job_name', 'Unknown')}")
                                
                                # 返回招聘会页面
                                self.driver.get(event['url'])
                                time.sleep(3)
                        except Exception as e:
                            logging.error(f"处理职位链接时出错: {e}")
                            # 尝试返回招聘会页面
                            self.driver.get(event['url'])
                            time.sleep(3)
            
            # 如果所有方式尝试后仍无法获取职位，提取网页中的职位文本信息
            if not job_data:
                logging.info("尝试从网页内容中提取职位信息")
                
                # 查找页面中可能包含职位信息的区域
                job_content_containers = self.driver.find_elements(By.CSS_SELECTOR, 
                    ".dm-text, .detail-content, .content-area, .detail-module")
                
                for i, container in enumerate(job_content_containers):
                    try:
                        text = container.text.strip()
                        if text and len(text) > 30:  # 确保文本有一定长度
                            # 检查是否包含职位相关关键词
                            if any(keyword in text for keyword in ["岗位", "职位", "招聘", "需求", "薪资", "待遇"]):
                                job_data.append({
                                    "event_id": event["id"],
                                    "event_title": event["title"],
                                    "job_id": f"text_{event['id']}_{i}",
                                    "job_name": f"招聘岗位{i+1}",
                                    "job_url": event["url"],
                                    "job_content": text,
                                    "extracted_from_text": True
                                })
                                logging.info(f"从文本中提取职位 {i+1}: 内容长度 {len(text)}")
                    except Exception as e:
                        logging.error(f"从文本容器 {i+1} 提取内容时出错: {e}")
            
            return job_data
            
        except Exception as e:
            logging.error(f"爬取招聘会职位失败: {e}")
            return job_data
    
    def get_job_details(self, job_id):
        """从职位详情页获取职位信息"""
        try:
            # 确保在职位详情页面
            if "detail/job" not in self.driver.current_url:
                job_url = f"https://sztu.bysjy.com.cn/detail/job?id={job_id}"
                self.driver.get(job_url)
                time.sleep(3)
            
            # 添加日志
            logging.info(f"正在获取职位 ID: {job_id} 的详情")
            
            # 如果不禁用调试功能，可以保存截图
            if not self.disable_debug:
                self.driver.save_screenshot(f"job_details_{job_id}_{time.strftime('%Y%m%d_%H%M%S')}.png")
            
            # 使用JavaScript提取职位详细信息
            job_details = self.driver.execute_script("""
                function getCleanText(selector) {
                    const elements = document.querySelectorAll(selector);
                    for (const element of elements) {
                        const text = element.textContent.trim();
                        if (text) return text;
                    }
                    return '';
                }
                
                // 尝试从职位详情页提取结构化数据
                let jobName = getCleanText('.job_name, .job-name, h1, .dm-tit');
                let companyName = getCleanText('.company-name, .comp-name');
                let salary = getCleanText('.item-salary, .salary');
                let location = getCleanText('.item-pos, .location');
                
                // 获取教育和福利信息
                let education = '';
                let welfare = '';
                
                // 尝试多种可能的选择器来获取教育信息
                const eduSelectors = [
                    '.tag-item', '.job-tag', '.info-item', '.requirements',
                    'p:contains("学历")', 'div:contains("学历要求")', 'span:contains("学历")'
                ];
                
                for (const selector of eduSelectors) {
                    const elements = document.querySelectorAll(selector);
                    for (const el of elements) {
                        const text = el.textContent.trim();
                        if (text.includes('本科') || text.includes('硕士') || text.includes('博士') || 
                            text.includes('大专') || text.includes('学历')) {
                            education = text;
                            break;
                        }
                    }
                    if (education) break;
                }
                
                // 获取福利标签
                const welfareSelectors = ['.job-welfare', '.welfare', '.benefit', '.tags'];
                for (const selector of welfareSelectors) {
                    const elements = document.querySelectorAll(selector);
                    if (elements.length) {
                        welfare = Array.from(elements).map(item => item.textContent.trim()).join(' ');
                        break;
                    }
                }
                
                // 尝试找到职位描述块
                let responsibilities = '';
                let requirements = '';
                let applicationInfo = '';
                let otherInfo = '';
                
                // 查找可能包含职位描述的元素
                const contentElements = document.querySelectorAll('.dm-text, .job-detail p, .content-text, .detail-content p, .dm-cont p');
                
                let currentSection = '';
                let sectionContent = [];
                
                for (const el of contentElements) {
                    const text = el.textContent.trim();
                    if (!text) continue;
                    
                    if (text.includes('岗位职责') || text.includes('职位职责') || text.includes('工作内容') || text === '职责:') {
                        if (currentSection && sectionContent.length) {
                            if (currentSection === '岗位职责') responsibilities = sectionContent.join('\\n');
                            else if (currentSection === '岗位要求') requirements = sectionContent.join('\\n');
                            else if (currentSection === '投递说明') applicationInfo = sectionContent.join('\\n');
                            else if (currentSection === '其他描述') otherInfo = sectionContent.join('\\n');
                        }
                        currentSection = '岗位职责';
                        sectionContent = [];
                    }
                    else if (text.includes('岗位要求') || text.includes('职位要求') || text.includes('任职资格') || 
                             text.includes('任职条件') || text === '要求:') {
                        if (currentSection && sectionContent.length) {
                            if (currentSection === '岗位职责') responsibilities = sectionContent.join('\\n');
                            else if (currentSection === '岗位要求') requirements = sectionContent.join('\\n');
                            else if (currentSection === '投递说明') applicationInfo = sectionContent.join('\\n');
                            else if (currentSection === '其他描述') otherInfo = sectionContent.join('\\n');
                        }
                        currentSection = '岗位要求';
                        sectionContent = [];
                    }
                    else if (text.includes('投递说明') || text.includes('联系方式') || text.includes('联系我们') || 
                             text.includes('申请流程')) {
                        if (currentSection && sectionContent.length) {
                            if (currentSection === '岗位职责') responsibilities = sectionContent.join('\\n');
                            else if (currentSection === '岗位要求') requirements = sectionContent.join('\\n');
                            else if (currentSection === '投递说明') applicationInfo = sectionContent.join('\\n');
                            else if (currentSection === '其他描述') otherInfo = sectionContent.join('\\n');
                        }
                        currentSection = '投递说明';
                        sectionContent = [];
                    }
                    else if (text.includes('其他描述') || text.includes('补充说明') || text.includes('其他')) {
                        if (currentSection && sectionContent.length) {
                            if (currentSection === '岗位职责') responsibilities = sectionContent.join('\\n');
                            else if (currentSection === '岗位要求') requirements = sectionContent.join('\\n');
                            else if (currentSection === '投递说明') applicationInfo = sectionContent.join('\\n');
                            else if (currentSection === '其他描述') otherInfo = sectionContent.join('\\n');
                        }
                        currentSection = '其他描述';
                        sectionContent = [];
                    }
                    else if (currentSection) {
                        sectionContent.push(text);
                    }
                }
                
                // 处理最后一个部分
                if (currentSection && sectionContent.length) {
                    if (currentSection === '岗位职责') responsibilities = sectionContent.join('\\n');
                    else if (currentSection === '岗位要求') requirements = sectionContent.join('\\n');
                    else if (currentSection === '投递说明') applicationInfo = sectionContent.join('\\n');
                    else if (currentSection === '其他描述') otherInfo = sectionContent.join('\\n');
                }
                
                // 如果上述方法无法提取到详细信息，尝试简单提取所有内容
                if (!responsibilities && !requirements) {
                    const contentDiv = document.querySelector('.job-detail, .detail-content, .content-area, .dm-cont');
                    if (contentDiv) {
                        const fullContent = contentDiv.textContent.trim();
                        // 将完整内容存储在其他描述中
                        otherInfo = fullContent;
                    }
                }
                
                return {
                    company_name: companyName || '未知公司',
                    job_name: jobName || '未知职位',
                    salary: salary || '',
                    location: location || '',
                    education: education || '',
                    welfare: welfare || '',
                    job_responsibilities: responsibilities || '',
                    job_requirements: requirements || '',
                    application_info: applicationInfo || '',
                    other_info: otherInfo || ''
                };
            """)
            
            # 如果JavaScript方法未能获取到完整信息，尝试使用BeautifulSoup
            if not job_details or not job_details.get('job_name') or job_details['job_name'] == '未知职位':
                logging.info("JavaScript方法未获取到完整职位信息，尝试使用BeautifulSoup")
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # 尝试获取职位名称和公司信息
                job_name_elem = soup.select_one('.job_name, .job-name, h1, .dm-tit')
                if job_name_elem:
                    job_details['job_name'] = job_name_elem.text.strip()
                
                company_elem = soup.select_one('.company-name, .comp-name, .company')
                if company_elem:
                    job_details['company_name'] = company_elem.text.strip()
                
                # 尝试获取详细内容
                content_elem = soup.select_one('.job-detail, .detail-content, .content-area, .dm-cont')
                if content_elem:
                    # 保存完整内容
                    full_content = content_elem.text.strip()
                    if not job_details.get('other_info'):
                        job_details['other_info'] = full_content

            return job_details
            
        except Exception as e:
            logging.error(f"获取职位详情失败: {e}")
            return {
                'company_name': '获取失败',
                'job_name': '获取失败',
                'error_message': str(e)
            }

if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description='在线招聘会职位爬虫')
        parser.add_argument('--max_pages', type=int, help='最大爬取页数，不设置则爬取全部页面')
        parser.add_argument('--headless', action='store_true', help='是否使用无头模式运行浏览器')
        parser.add_argument('--disable_debug', action='store_false', help='禁用调试功能，不保存截图和页面源码')
        parser.add_argument('--output', type=str, default='recruitment_data.json', 
                          help='指定输出JSON文件的路径，默认为当前目录下的recruitment_data.json')
        args = parser.parse_args()
        
        if args.max_pages:
            logging.info(f"设置最大爬取页数: {args.max_pages}")
        if args.headless:
            logging.info("将使用无头模式运行浏览器")
        if args.disable_debug:
            logging.info("已禁用调试功能，不会保存截图和页面源码")
        
        logging.info(f"数据将保存到: {args.output}")
        
        # 确保输出目录存在
        output_dir = os.path.dirname(args.output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"创建输出目录: {output_dir}")
        
        # 初始化爬虫并开始爬取
        crawler = OnlineRecruitmentCrawler(headless=args.headless, disable_debug=args.disable_debug)
        crawler.crawl(args.max_pages, output_file=args.output)
        
    except KeyboardInterrupt:
        logging.info("程序被用户中断")
    except Exception as e:
        logging.error(f"程序执行出错: {e}")
