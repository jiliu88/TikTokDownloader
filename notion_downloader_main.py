"""
文件: notion_downloader_main.py
作用: Notion抖音视频下载器的入口脚本，使用tiktok_downloader_api实现下载功能
自动从notion_config.json获取配置并执行下载
"""

import asyncio
import os
import json
from pathlib import Path
import httpx
from typing import Optional, Dict, Any, List

from src.tools import ColorfulConsole
from tiktok_downloader_api import download_douyin_video, download_tiktok_video, _download_video


class NotionManager:
    """Notion数据库管理器"""
    
    def __init__(self, token: str, database_id: str, console: ColorfulConsole):
        """
        初始化Notion管理器
        
        Args:
            token: Notion API令牌
            database_id: Notion数据库ID
            console: 控制台对象
        """
        self.token = token
        self.database_id = database_id
        self.console = console
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
    
    async def query_database(self, filter_params: Optional[Dict] = None) -> List[Dict]:
        """
        查询Notion数据库
        
        Args:
            filter_params: 过滤参数
            
        Returns:
            查询结果列表
        """
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = {}
        
        if filter_params:
            payload["filter"] = filter_params
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload)
                
                if response.status_code != 200:
                    self.console.error(f"查询Notion数据库失败: {response.text}")
                    return []
                    
                data = response.json()
                return data.get("results", [])
        except Exception as e:
            self.console.error(f"查询Notion数据库时出错: {str(e)}")
            import traceback
            self.console.error(traceback.format_exc())
            return []
    
    def get_url_from_page(self, page: Dict) -> Optional[str]:
        """
        从页面中获取视频URL
        
        Args:
            page: 页面数据
            
        Returns:
            视频URL或None
        """
        properties = page.get("properties", {})
        
        # 根据截图中的数据库结构，主要从"抖音url"属性获取URL
        if url_prop := properties.get("抖音url"):
            # 检查属性类型
            if "url" in url_prop:
                return url_prop["url"]
            elif "rich_text" in url_prop and url_prop["rich_text"]:
                for text in url_prop["rich_text"]:
                    if "text" in text and "content" in text["text"]:
                        content = text["text"]["content"]
                        if content.startswith(("http://", "https://")):
                            return content
        
        return None
    
    async def update_page_status(self, page_id: str, status: str) -> bool:
        """
        更新页面状态
        
        Args:
            page_id: 页面ID
            status: 新状态
            
        Returns:
            是否更新成功
        """
        # 首先获取页面信息，确定状态属性的类型
        url = f"https://api.notion.com/v1/pages/{page_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                
                if response.status_code != 200:
                    self.console.error(f"获取Notion页面失败: {response.text}")
                    return False
                
                page = response.json()
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
                    self.console.error(f"未找到抖音状态属性或不支持的属性类型")
                    return False
                
                # 更新页面
                payload = {
                    "properties": properties
                }
                
                response = await client.patch(url, headers=self.headers, json=payload)
                
                if response.status_code != 200:
                    self.console.error(f"更新Notion页面失败: {response.text}")
                    return False
                
                return True
        except Exception as e:
            self.console.error(f"更新Notion页面状态时出错: {str(e)}")
            import traceback
            self.console.error(traceback.format_exc())
            return False


async def download_and_update(
    notion: NotionManager, 
    page: Dict, 
    download_dir: str, 
    console: ColorfulConsole,
    is_tiktok: bool = False
) -> None:
    """
    下载视频并更新Notion页面状态
    
    Args:
        notion: Notion管理器
        page: 页面数据
        download_dir: 下载目录
        console: 控制台对象
        is_tiktok: 是否为TikTok视频
    """
    # 获取视频URL
    url = notion.get_url_from_page(page)
    if not url:
        console.info(f"页面 {page['id']} 没有找到视频URL，跳过")
        return
    
    console.info(f"开始下载视频: {url}")
    
    # 直接调用异步下载函数，而不是通过download_douyin_video或download_tiktok_video
    result = await _download_video(url, is_tiktok, download_dir)
    
    page_id = page["id"]
    
    if result["success"]:
        console.print(f"视频下载成功: {result['video_path']}")
        # 更新Notion页面状态为"已下载"
        if await notion.update_page_status(page_id, "已下载"):
            console.info(f"已更新页面状态为: 已下载")
        else:
            console.error(f"更新页面状态失败")
    else:
        console.error(f"视频下载失败: {url}")
        console.error(f"错误信息: {result['message']}")
        # 更新Notion页面状态为"下载失败"
        if await notion.update_page_status(page_id, "下载失败"):
            console.info(f"已更新页面状态为: 下载失败")
        else:
            console.error(f"更新页面状态失败")


async def main():
    """
    主函数 - 从notion_config.json获取配置并自动执行下载
    """
    console = ColorfulConsole()
    
    # 从配置文件加载设置
    config_path = Path("notion_config.json")
    if not config_path.exists():
        console.error(f"配置文件 {config_path} 不存在！")
        console.info("请创建配置文件，包含以下内容：")
        console.info("""
{
    "notion_token": "你的Notion API令牌",
    "database_id": "你的数据库ID",
    "download_dir": "Download/Notion",
    "is_tiktok": false
}
        """)
        return
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        notion_token = config.get("notion_token", "")
        database_id = config.get("database_id", "")
        download_dir = config.get("download_dir", "Download/Notion")
        is_tiktok = config.get("is_tiktok", False)
        
        console.info(f"已从配置文件 {config_path} 加载设置")
        console.info(f"数据库ID: {database_id}")
        console.info(f"下载目录: {download_dir}")
        console.info(f"视频类型: {'TikTok' if is_tiktok else '抖音'}")
        
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        console.error(f"读取配置文件失败: {str(e)}")
        return
    
    # 检查是否有必要的配置
    if not notion_token:
        console.error("错误: 未设置Notion API令牌")
        return
    
    if not database_id:
        console.error("错误: 未设置Notion数据库ID")
        return
    
    # 创建下载目录
    os.makedirs(download_dir, exist_ok=True)
    
    try:
        # 创建Notion管理器
        notion = NotionManager(notion_token, database_id, console)
        
        # 查询待下载的视频
        filter_params = {
            "property": "抖音状态",
            "status": {
                "equals": "待下载"
            }
        }
        
        pages = await notion.query_database(filter_params)
        
        if not pages:
            console.info("没有找到待下载的视频")
            return
            
        console.info(f"找到 {len(pages)} 个待下载的视频")
        
        # 下载视频并更新状态
        for page in pages:
            await download_and_update(notion, page, download_dir, console, is_tiktok)
            
    except Exception as e:
        console.error(f"运行下载器时出错: {str(e)}")
        import traceback
        console.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())
