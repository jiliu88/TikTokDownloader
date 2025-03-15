"""
文件: notion_downloader.py
作用: 通过Notion API获取表格数据，下载抖音视频并上传到Notion表格
"""

import os
import json
import asyncio
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from src.application.TikTokDownloader import TikTokDownloader
from src.tools import ColorfulConsole
from src.link import Extractor, ExtractorTikTok
from src.extract import Extractor as DataExtractor
from src.downloader import Downloader
from src.config import Parameter
from src.manager import Database
from types import SimpleNamespace


class NotionDownloader:
    """
    Notion抖音视频下载器
    通过Notion API获取表格数据，下载抖音视频并上传到Notion表格
    """
    
    def __init__(self, notion_token: str, database_id: str, download_dir: str = "Download/Notion"):
        """
        初始化Notion下载器
        
        Args:
            notion_token: Notion API的访问令牌
            database_id: Notion数据库ID
            download_dir: 视频下载目录
        """
        self.notion_token = notion_token  # Notion API访问令牌
        self.database_id = database_id  # Notion数据库ID
        self.download_dir = download_dir  # 下载目录
        self.headers = {
            "Authorization": f"Bearer {notion_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        self.console = ColorfulConsole()  # 彩色控制台输出
        
        # 确保下载目录存在
        os.makedirs(download_dir, exist_ok=True)
        
        # 初始化TikTokDownloader实例
        self.downloader = None
        self.parameter = None
        self.database = None
        self.link_extractor = None
        self.data_extractor = None
    
    async def __aenter__(self):
        """
        异步上下文管理器入口
        """
        try:
            # 初始化Notion客户端
            try:
                from notion_client import Client
                self.notion = Client(auth=self.notion_token)
            except ImportError:
                self.console.error("未安装notion_client库，请使用pip install notion-client安装")
                self.notion = None
            except Exception as e:
                self.console.error(f"初始化Notion客户端失败: {str(e)}")
                self.notion = None
            
            # 不在这里初始化TikTokDownloader和Extractor
            self.downloader = None
            self.parameter = None
            self.database = None
            self.link_extractor = None
            self.data_extractor = None
            
            return self
        except Exception as e:
            self.console.error(f"初始化NotionDownloader时出错: {str(e)}")
            # 重新抛出异常，让调用者处理
            raise
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出
        """
        if self.downloader:
            await self.downloader.__aexit__(exc_type, exc_val, exc_tb)
    
    async def query_database(self, status: str = None) -> List[Dict]:
        """
        查询Notion数据库中的页面
        
        Args:
            status: 筛选的状态，例如"待下载"、"已下载"等
            
        Returns:
            符合条件的页面列表
        """
        try:
            if not self.notion:
                self.console.error("Notion客户端未初始化")
                return []
                
            filter_params = {}
            if status:
                filter_params = {
                    "filter": {
                        "property": "抖音状态",
                        "status": {
                            "equals": status
                        }
                    }
                }
            
            response = await self.notion.databases.query(
                database_id=self.database_id,
                **filter_params
            )
            
            return response.get("results", [])
        except Exception as e:
            self.console.error(f"查询数据库失败: {str(e)}")
            return []
    
    def get_url_from_page(self, page: Dict) -> Optional[str]:
        """
        从页面中获取抖音视频URL
        
        Args:
            page: Notion页面数据
            
        Returns:
            抖音视频URL，如果没有找到则返回None
        """
        try:
            properties = page.get("properties", {})
            
            # 尝试从不同的属性中获取URL
            url_property_names = ["抖音链接", "URL", "视频链接", "链接"]
            
            for name in url_property_names:
                if name in properties:
                    prop = properties[name]
                    
                    # 处理不同类型的属性
                    if "url" in prop:
                        return prop["url"]
                    elif "rich_text" in prop and prop["rich_text"]:
                        return prop["rich_text"][0]["plain_text"]
                    elif "title" in prop and prop["title"]:
                        return prop["title"][0]["plain_text"]
            
            return None
        except Exception as e:
            self.console.error(f"从页面获取URL失败: {str(e)}")
            return None
    
    async def update_page_status(self, page_id: str, status: str) -> bool:
        """
        更新页面的状态
        
        Args:
            page_id: 页面ID
            status: 新的状态值
            
        Returns:
            是否更新成功
        """
        try:
            # 先获取页面详情，确定属性类型
            page = await self.notion.pages.retrieve(page_id=page_id)
            if not page:
                self.console.error(f"无法获取页面详情: {page_id}")
                return False
            
            # 检查"抖音状态"属性的类型
            status_property = page.get("properties", {}).get("抖音状态", {})
            status_type = None
            
            if "select" in status_property:
                status_type = "select"
            elif "rich_text" in status_property:
                status_type = "rich_text"
            elif "title" in status_property:
                status_type = "title"
            elif "status" in status_property:
                status_type = "status"
            
            # 准备更新属性
            properties = {}
            if status_type == "select":
                properties = {
                    "抖音状态": {
                        "select": {
                            "name": status
                        }
                    }
                }
            elif status_type == "rich_text":
                properties = {
                    "抖音状态": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": status
                                }
                            }
                        ]
                    }
                }
            elif status_type == "title":
                properties = {
                    "抖音状态": {
                        "title": [
                            {
                                "text": {
                                    "content": status
                                }
                            }
                        ]
                    }
                }
            elif status_type == "status":
                properties = {
                    "抖音状态": {
                        "status": {
                            "name": status
                        }
                    }
                }
            else:
                self.console.warning(f"未知的属性类型: {status_type}")
                return False
            
            # 更新页面
            await self.notion.pages.update(
                page_id=page_id,
                properties=properties
            )
            
            self.console.info(f"已更新页面状态为: {status}")
            return True
        except Exception as e:
            self.console.error(f"更新页面状态失败: {str(e)}")
            return False
    
    async def update_page_property(self, page_id: str, property_name: str, value: str) -> bool:
        """
        更新页面的属性
        
        Args:
            page_id: 页面ID
            property_name: 属性名称
            value: 属性值
            
        Returns:
            是否更新成功
        """
        try:
            # 先获取页面详情，确定属性类型
            page = await self.notion.pages.retrieve(page_id=page_id)
            if not page:
                self.console.error(f"无法获取页面详情: {page_id}")
                return False
            
            # 检查属性的类型
            property_data = page.get("properties", {}).get(property_name, {})
            property_type = None
            
            if "rich_text" in property_data:
                property_type = "rich_text"
            elif "title" in property_data:
                property_type = "title"
            elif "url" in property_data:
                property_type = "url"
            
            # 准备更新属性
            properties = {}
            if property_type == "rich_text":
                properties = {
                    property_name: {
                        "rich_text": [
                            {
                                "text": {
                                    "content": value
                                }
                            }
                        ]
                    }
                }
            elif property_type == "title":
                properties = {
                    property_name: {
                        "title": [
                            {
                                "text": {
                                    "content": value
                                }
                            }
                        ]
                    }
                }
            elif property_type == "url":
                properties = {
                    property_name: {
                        "url": f"file://{value}"
                    }
                }
            else:
                self.console.warning(f"未知的属性类型: {property_type}")
                return False
            
            # 更新页面
            await self.notion.pages.update(
                page_id=page_id,
                properties=properties
            )
            
            self.console.info(f"已更新页面属性 {property_name}: {value}")
            return True
        except Exception as e:
            self.console.error(f"更新页面属性失败: {str(e)}")
            return False
    
    async def get_page(self, page_id: str) -> Optional[Dict]:
        """
        获取Notion页面详情
        
        Args:
            page_id: 页面ID
            
        Returns:
            页面详情，如果获取失败则返回None
        """
        url = f"https://api.notion.com/v1/pages/{page_id}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            
            if response.status_code != 200:
                self.console.error(f"获取Notion页面失败: {response.text}")
                return None
                
            return response.json()
    
    async def update_page_properties(self, page_id: str, properties: Dict) -> bool:
        """
        更新Notion页面属性
        
        Args:
            page_id: 页面ID
            properties: 要更新的属性
            
        Returns:
            更新是否成功
        """
        url = f"https://api.notion.com/v1/pages/{page_id}"
        
        payload = {
            "properties": properties
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(url, headers=self.headers, json=payload)
            
            if response.status_code != 200:
                self.console.error(f"更新Notion页面失败: {response.text}")
                return False
                
            return True
    
    async def upload_file_to_notion(self, page_id: str, file_path: str, property_name: str) -> bool:
        """
        上传文件到Notion页面
        
        Args:
            page_id: 页面ID
            file_path: 文件路径
            property_name: 属性名称
            
        Returns:
            上传是否成功
        """
        # 目前Notion API不直接支持文件上传，这里可以实现为更新文件URL属性
        # 实际应用中，你可能需要先将文件上传到其他存储服务，然后将URL更新到Notion
        
        # 这里简化为更新一个文本属性，记录文件已下载的路径
        properties = {
            property_name: {
                "rich_text": [
                    {
                        "text": {
                            "content": f"已下载: {file_path}"
                        }
                    }
                ]
            }
        }
        
        return await self.update_page_properties(page_id, properties)
    
    async def download_video(self, url: str) -> Optional[str]:
        """
        下载抖音视频
        
        Args:
            url: 抖音视频URL
            
        Returns:
            下载的视频文件路径，如果下载失败则返回None
        """
        # 直接使用simple_download_video方法，它会在内部创建TikTokDownloader实例
        return await self.simple_download_video(url)
    
    async def simple_download_video(self, url: str) -> Optional[str]:
        """
        使用TikTokDownloader下载抖音视频
        
        Args:
            url: 抖音视频URL
            
        Returns:
            下载的视频文件路径，如果下载失败则返回None
        """
        try:
            self.console.info(f"使用TikTokDownloader下载视频: {url}")
            
            # 创建下载目录
            download_dir = Path(self.download_dir)
            os.makedirs(download_dir, exist_ok=True)
            
            # 初始化TikTokDownloader
            from src.application.TikTokDownloader import TikTokDownloader
            from src.config import Parameter, Settings
            from src.manager import Database
            from src.module import Cookie
            from src.record import LoggerManager
            from src.storage import RecordManager
            from src.link import Extractor as LinkExtractor
            from src.extract import Extractor as DataExtractor
            from src.application.main_complete import TikTok
            from src.custom import PROJECT_ROOT
            from src.tools import safe_pop
            
            # 创建TikTokDownloader实例
            downloader = TikTokDownloader()
            
            # 初始化必要的组件
            await downloader.database.__aenter__()
            await downloader.read_config()
            
            # 设置下载目录
            settings_data = downloader.settings.read()
            settings_data["root"] = str(download_dir)
            
            # 初始化参数
            downloader.check_config()
            downloader.parameter = Parameter(
                downloader.settings,
                downloader.cookie,
                logger=downloader.logger,
                console=downloader.console,
                **settings_data,
                recorder=downloader.recorder,
            )
            
            # 设置运行命令
            downloader.run_command = ["6", url]  # 6是终端交互模式，然后是URL
            
            # 创建TikTok实例
            tiktok = TikTok(
                downloader.parameter,
                downloader.database,
            )
            
            # 创建记录器
            root, params, logger = tiktok.record.run(downloader.parameter)
            
            # 使用__detail_inquire方法下载视频
            async with logger(root, console=downloader.console, **params) as record:
                # 提取视频ID
                ids = await tiktok.links.run(url)
                if not any(ids):
                    self.console.warning(f"{url} 提取作品ID失败")
                    return None
                
                self.console.info(f"共提取到 {len(ids)} 个作品，开始处理！")
                
                # 处理视频
                await tiktok._handle_detail(ids, False, record)
            
            # 查找下载的视频文件
            video_files = list(download_dir.glob("**/*.mp4"))
            if not video_files:
                # 尝试查找其他视频格式
                video_files = list(download_dir.glob("**/*.mp4")) + \
                              list(download_dir.glob("**/*.webm")) + \
                              list(download_dir.glob("**/*.mov"))
            
            if video_files:
                # 按修改时间排序，获取最新的文件
                video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                video_path = str(video_files[0])
                self.console.info(f"找到下载的视频文件: {video_path}")
                return video_path
            
            # 如果上面的方法失败，尝试使用命令行方式
            self.console.info("尝试使用命令行方式下载视频")
            
            # 使用subprocess直接调用main.py
            import subprocess
            import sys
            import tempfile
            
            # 创建临时文件存储命令
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as f:
                f.write(url)
                temp_file = f.name
            
            # 构建命令 - 使用终端交互模式
            cmd = [
                sys.executable, 
                "-c", 
                f"""
import asyncio
from src.application.TikTokDownloader import TikTokDownloader
from src.application.main_complete import TikTok
from src.tools import safe_pop

async def main():
    async with TikTokDownloader() as downloader:
        downloader.project_info()
        downloader.check_config()
        await downloader.check_settings(False)
        
        # 设置下载目录
        downloader.parameter.root = "{str(download_dir)}"
        
        # 创建TikTok实例
        tiktok = TikTok(downloader.parameter, downloader.database)
        
        # 读取URL
        with open("{temp_file}", "r") as f:
            url = f.read().strip()
        
        # 创建记录器
        root, params, logger = tiktok.record.run(downloader.parameter)
        
        # 下载视频
        async with logger(root, console=downloader.console, **params) as record:
            ids = await tiktok.links.run(url)
            if any(ids):
                await tiktok._handle_detail(ids, False, record)

asyncio.run(main())
                """
            ]
            
            # 执行命令
            self.console.info(f"执行Python脚本下载视频")
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            # 获取输出
            stdout, stderr = process.communicate()
            
            # 删除临时文件
            try:
                os.unlink(temp_file)
            except:
                pass
            
            if process.returncode != 0:
                self.console.error(f"下载失败，返回码: {process.returncode}")
                self.console.error(f"错误信息: {stderr}")
                self.console.info(f"输出信息: {stdout}")
                return None
                
            # 再次查找下载的视频文件
            video_files = list(download_dir.glob("**/*.mp4"))
            if not video_files:
                # 尝试查找其他视频格式
                video_files = list(download_dir.glob("**/*.mp4")) + \
                              list(download_dir.glob("**/*.webm")) + \
                              list(download_dir.glob("**/*.mov"))
            
            if video_files:
                # 按修改时间排序，获取最新的文件
                video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                video_path = str(video_files[0])
                self.console.info(f"找到下载的视频文件: {video_path}")
                return video_path
            
            self.console.warning("未找到下载的视频文件")
            return None
            
        except Exception as e:
            self.console.error(f"下载视频失败: {str(e)}")
            import traceback
            self.console.error(traceback.format_exc())
            return None
    
    async def process_notion_database(self):
        """
        处理Notion数据库中的视频
        查询需要下载的视频，下载后更新状态
        """
        # 查询未下载的视频
        filter_params = {
            "and": [
                {
                    "property": "抖音状态",
                    "select": {
                        "equals": "待下载"
                    }
                }
            ]
        }
        
        pages = await self.query_database(filter_params)
        
        if not pages:
            self.console.info("没有找到需要下载的视频")
            return
        
        self.console.info(f"找到 {len(pages)} 个需要下载的视频")
        
        for page in pages:
            page_id = page["id"]
            
            # 获取视频URL
            # 注意：属性名称和结构需要根据你的Notion数据库结构进行调整
            try:
                url_property = page["properties"].get("抖音url", {})
                url = url_property.get("url", "") or url_property.get("rich_text", [{}])[0].get("text", {}).get("content", "")
                
                if not url:
                    self.console.warning(f"页面 {page_id} 没有URL")
                    continue
                
                # 更新状态为"下载中"
                await self.update_page_properties(page_id, {
                    "抖音状态": {
                        "select": {
                            "name": "下载中"
                        }
                    }
                })
                
                # 下载视频
                self.console.info(f"正在下载: {url}")
                video_path = await self.download_video(url)
                
                if video_path:
                    # 更新状态和文件路径
                    await self.update_page_properties(page_id, {
                        "抖音状态": {
                            "select": {
                                "name": "待审核"
                            }
                        },
                        "File": {
                            "rich_text": [
                                {
                                    "text": {
                                        "content": video_path
                                    }
                                }
                            ]
                        }
                    })
                    self.console.print(f"下载成功: {video_path}")
                else:
                    # 更新状态为"下载失败"
                    await self.update_page_properties(page_id, {
                        "抖音状态": {
                            "select": {
                                "name": "下载失败"
                            }
                        }
                    })
                    self.console.error(f"下载失败: {url}")
            
            except Exception as e:
                self.console.error(f"处理页面 {page_id} 时出错: {str(e)}")
                # 更新状态为"下载失败"
                await self.update_page_properties(page_id, {
                    "抖音状态": {
                        "select": {
                            "name": "下载失败"
                        }
                    }
                })
    
    async def get_videos_to_download(self) -> List[Dict[str, str]]:
        """
        获取需要下载的视频列表
        
        Returns:
            包含视频ID和URL的字典列表
        """
        try:
            # 查询所有页面，不使用过滤条件
            pages = await self.query_database()
            
            if not pages:
                self.console.info("没有找到任何视频")
                return []
            
            self.console.info(f"从Notion数据库中获取到 {len(pages)} 个页面")
            
            # 打印第一个页面的属性结构，用于调试
            if pages:
                self.console.info("页面属性结构示例:")
                properties = pages[0].get("properties", {})
                for prop_name, prop_value in properties.items():
                    prop_type = next(iter(prop_value.keys())) if prop_value else "unknown"
                    self.console.info(f"  - {prop_name}: {prop_type}")
                    
                    # 如果是"抖音状态"属性，打印更详细的信息
                    if prop_name == "抖音状态":
                        self.console.info(f"    详细信息: {json.dumps(prop_value, ensure_ascii=False)}")
            
            # 在代码中过滤状态为"待下载"的页面
            videos = []
            for page in pages:
                page_id = page["id"]
                
                try:
                    # 获取状态属性
                    status = None
                    status_property = page["properties"].get("抖音状态", {})
                    
                    # 打印状态属性的详细信息
                    self.console.info(f"页面 {page_id} 的状态属性: {json.dumps(status_property, ensure_ascii=False)}")
                    
                    # 尝试不同的属性类型
                    if "select" in status_property:
                        status = status_property["select"].get("name", "") if status_property["select"] else ""
                    elif "rich_text" in status_property:
                        rich_texts = status_property["rich_text"]
                        if rich_texts and len(rich_texts) > 0:
                            status = rich_texts[0].get("text", {}).get("content", "")
                    elif "title" in status_property:
                        titles = status_property["title"]
                        if titles and len(titles) > 0:
                            status = titles[0].get("text", {}).get("content", "")
                    elif "status" in status_property:
                        status = status_property["status"].get("name", "")
                    
                    self.console.info(f"页面 {page_id} 的状态值: {status}")
                    
                    # 如果状态不是"待下载"，则跳过
                    if status != "待下载":
                        self.console.info(f"页面 {page_id} 的状态不是'待下载'，跳过")
                        continue
                    
                    # 获取视频URL
                    url = None
                    url_property = page["properties"].get("抖音url", {})
                    
                    # 打印URL属性的详细信息
                    self.console.info(f"页面 {page_id} 的URL属性: {json.dumps(url_property, ensure_ascii=False)}")
                    
                    # 尝试不同的属性类型
                    if "url" in url_property:
                        url = url_property["url"]
                    elif "rich_text" in url_property:
                        rich_texts = url_property["rich_text"]
                        if rich_texts and len(rich_texts) > 0:
                            url = rich_texts[0].get("text", {}).get("content", "")
                    elif "title" in url_property:
                        titles = url_property["title"]
                        if titles and len(titles) > 0:
                            url = titles[0].get("text", {}).get("content", "")
                    
                    self.console.info(f"页面 {page_id} 的URL值: {url}")
                    
                    if not url:
                        self.console.warning(f"页面 {page_id} 没有URL")
                        continue
                    
                    videos.append({
                        "id": page_id,
                        "url": url
                    })
                    
                except Exception as e:
                    self.console.error(f"处理页面 {page_id} 时出错: {str(e)}")
            
            self.console.info(f"找到 {len(videos)} 个需要下载的视频")
            return videos
            
        except Exception as e:
            self.console.error(f"获取视频列表时出错: {str(e)}")
            return []
    
    async def upload_video_to_notion(self, page_id: str, video_path: str) -> bool:
        """
        将视频上传到Notion
        
        Args:
            page_id: Notion页面ID
            video_path: 视频文件路径
            
        Returns:
            上传是否成功
        """
        try:
            # 目前Notion API不直接支持文件上传
            # 这里我们只更新文件路径属性
            properties = {
                "File": {
                    "rich_text": [
                        {
                            "text": {
                                "content": video_path
                            }
                        }
                    ]
                }
            }
            
            return await self.update_page_properties(page_id, properties)
        except Exception as e:
            self.console.error(f"上传视频到Notion失败: {str(e)}")
            return False
    
    async def run(self):
        """
        运行Notion下载器
        """
        self.console.info("开始从Notion获取视频并下载")
        await self.process_notion_database()
        self.console.print("处理完成")

    def get_url_from_page(self, page: dict) -> str:
        """
        从Notion页面中提取URL
        
        Args:
            page: Notion页面数据
            
        Returns:
            提取的URL，如果没有找到则返回空字符串
        """
        try:
            # 获取视频URL
            url_property = page.get("properties", {}).get("抖音url", {})
            
            # 尝试不同的属性类型
            if "url" in url_property:
                return url_property["url"] or ""
            elif "rich_text" in url_property:
                rich_texts = url_property["rich_text"]
                if rich_texts and len(rich_texts) > 0:
                    return rich_texts[0].get("text", {}).get("content", "")
            elif "title" in url_property:
                titles = url_property["title"]
                if titles and len(titles) > 0:
                    return titles[0].get("text", {}).get("content", "")
                    
            return ""
        except Exception as e:
            self.console.error(f"从页面提取URL时出错: {str(e)}")
            return ""


async def main():
    """
    主函数
    """
    # 从环境变量或配置文件获取Notion API令牌和数据库ID
    notion_token = os.environ.get("NOTION_TOKEN", "")
    database_id = os.environ.get("NOTION_DATABASE_ID", "")
    
    if not notion_token or not database_id:
        # 尝试从配置文件加载
        try:
            with open("notion_config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                notion_token = config.get("notion_token", "")
                database_id = config.get("database_id", "")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    if not notion_token or not database_id:
        print("错误: 未设置Notion API令牌或数据库ID")
        print("请设置环境变量NOTION_TOKEN和NOTION_DATABASE_ID")
        print("或创建notion_config.json文件，包含notion_token和database_id字段")
        return
    
    async with NotionDownloader(notion_token, database_id) as downloader:
        await downloader.run()


if __name__ == "__main__":
    asyncio.run(main())
