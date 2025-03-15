"""
文件: notion_downloader_main.py
作用: Notion抖音视频下载器的入口脚本，使用tiktok_downloader_api实现下载功能
自动从notion_config.json获取配置并执行下载

这个脚本可以自动从Notion数据库中获取抖音视频链接，下载视频，并更新Notion中的状态。
工作流程:
1. 从配置文件加载Notion API令牌、数据库ID和下载目录
2. 查询Notion数据库中状态为"待下载"的条目
3. 下载每个条目中的抖音视频
4. 根据下载结果更新Notion中的状态为"已下载"或"下载失败"
"""

import asyncio  # 用于异步编程
import os  # 用于文件系统操作
import json  # 用于解析JSON配置文件
from pathlib import Path  # 用于处理文件路径
import httpx  # 用于HTTP请求
from typing import Optional, Dict, Any, List  # 类型提示

from src.tools import ColorfulConsole  # 导入彩色控制台输出工具
from tiktok_downloader_api import _download_video  # 导入视频下载函数


class NotionManager:
    """
    Notion数据库管理器
    
    负责与Notion API交互，包括查询数据库、获取页面信息和更新页面状态
    """
    
    def __init__(self, token: str, database_id: str, console: ColorfulConsole):
        """
        初始化Notion管理器
        
        Args:
            token: Notion API令牌，用于认证
            database_id: Notion数据库ID，指定要操作的数据库
            console: 控制台对象，用于输出日志
        """
        self.token = token  # Notion API令牌
        self.database_id = database_id  # Notion数据库ID
        self.console = console  # 控制台对象
        # 设置API请求头
        self.headers = {
            "Authorization": f"Bearer {token}",  # 认证信息
            "Content-Type": "application/json",  # 内容类型
            "Notion-Version": "2022-06-28"  # API版本
        }
    
    async def query_database(self, filter_params: Optional[Dict] = None) -> List[Dict]:
        """
        查询Notion数据库，获取符合条件的页面
        
        Args:
            filter_params: 过滤参数，用于筛选特定条件的页面
            
        Returns:
            查询结果列表，每个元素是一个页面的数据
        """
        # 构建API请求URL
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        payload = {}  # 请求体
        
        # 如果有过滤参数，添加到请求体中
        if filter_params:
            payload["filter"] = filter_params
        
        try:
            # 发送异步HTTP请求
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.headers, json=payload)
                
                # 检查响应状态
                if response.status_code != 200:
                    self.console.error(f"查询Notion数据库失败: {response.text}")
                    return []
                    
                # 解析响应数据
                data = response.json()
                return data.get("results", [])  # 返回结果列表
        except Exception as e:
            # 处理异常
            self.console.error(f"查询Notion数据库时出错: {str(e)}")
            import traceback
            self.console.error(traceback.format_exc())
            return []  # 出错时返回空列表
    
    def get_url_from_page(self, page: Dict) -> Optional[str]:
        """
        从Notion页面中提取抖音视频URL
        
        Args:
            page: 页面数据，包含各种属性
            
        Returns:
            抖音视频URL或None（如果未找到）
        """
        # 获取页面的所有属性
        properties = page.get("properties", {})
        
        # 根据数据库结构，主要从"抖音url"属性获取URL
        if url_prop := properties.get("抖音url"):
            # 检查属性类型是否为URL类型
            if "url" in url_prop:
                return url_prop["url"]
            # 检查属性类型是否为富文本类型
            elif "rich_text" in url_prop and url_prop["rich_text"]:
                for text in url_prop["rich_text"]:
                    if "text" in text and "content" in text["text"]:
                        content = text["text"]["content"]
                        # 检查内容是否为URL格式
                        if content.startswith(("http://", "https://")):
                            return content
        
        # 未找到URL时返回None
        return None
    
    async def update_page_status(self, page_id: str, status: str) -> bool:
        """
        更新Notion页面的状态
        
        Args:
            page_id: 页面ID，用于定位要更新的页面
            status: 新状态，如"已下载"或"下载失败"
            
        Returns:
            是否更新成功
        """
        # 构建API请求URL
        url = f"https://api.notion.com/v1/pages/{page_id}"
        
        try:
            # 准备更新数据
            properties = {
                "抖音状态": {
                    "status": {
                        "name": status
                    }
                }
            }
            
            # 准备更新请求体
            payload = {
                "properties": properties
            }
            
            # 发送更新请求
            async with httpx.AsyncClient() as client:
                response = await client.patch(url, headers=self.headers, json=payload)
            
            # 检查更新结果
            if response.status_code != 200:
                self.console.error(f"更新Notion页面失败: {response.text}")
                return False
            
            # 更新成功
            return True
            
        except Exception as e:
            # 处理异常
            self.console.error(f"更新Notion页面状态时出错: {str(e)}")
            import traceback
            self.console.error(traceback.format_exc())
            return False  # 出错时返回失败

    async def get_video_id(self, url: str) -> Optional[str]:
        """
        从抖音链接中获取视频ID
        
        Args:
            url: 抖音视频链接
            
        Returns:
            视频ID或None（如果获取失败）
        """
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url)
                final_url = str(response.url)
                video_id = final_url.split("/video/")[1].split("?")[0]
                return video_id
        except Exception as e:
            self.console.error(f"获取视频ID时出错: {str(e)}")
            return None
    
    async def update_video_id(self, page_id: str, video_id: str) -> bool:
        """
        更新Notion页面的视频ID
        
        Args:
            page_id: 页面ID
            video_id: 视频ID
            
        Returns:
            是否更新成功
        """
        url = f"https://api.notion.com/v1/pages/{page_id}"
        
        try:
            properties = {
                "抖音id": {
                    "rich_text": [
                        {
                            "text": {
                                "content": video_id
                            }
                        }
                    ]
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    url, 
                    headers=self.headers, 
                    json={"properties": properties}
                )
            
            return response.status_code == 200
        except Exception as e:
            self.console.error(f"更新视频ID时出错: {str(e)}")
            return False


async def download_and_update(
    notion: NotionManager, 
    page: Dict, 
    download_dir: str, 
    console: ColorfulConsole
) -> None:
    """
    下载视频并更新Notion页面状态
    
    Args:
        notion: Notion管理器，用于与Notion API交互
        page: 页面数据，包含视频URL等信息
        download_dir: 下载目录，视频将保存到此目录
        console: 控制台对象，用于输出日志
    """
    # 从页面中获取视频URL
    url = notion.get_url_from_page(page)
    if not url:
        # 未找到URL时输出日志并跳过
        console.info(f"页面 {page['id']} 没有找到视频URL，跳过")
        return
    
    # 输出开始下载的日志
    console.info(f"开始下载视频: {url}")
    
    # 调用异步下载函数下载视频
    result = await _download_video(url, False, download_dir)
    
    # 获取页面ID，用于更新状态
    page_id = page["id"]
    
    # 根据下载结果更新页面状态
    if result["success"]:
        # 下载成功
        console.print(f"视频下载成功: {result['video_path']}")
        # 更新Notion页面状态为"已下载"
        if await notion.update_page_status(page_id, "已下载"):
            console.info(f"已更新页面状态为: 已下载")
        else:
            console.error(f"更新页面状态失败")
    else:
        # 下载失败
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
    
    工作流程:
    1. 加载配置文件
    2. 创建Notion管理器
    3. 先获取所有需要获取视频ID的数据
    4. 获取并更新视频ID
    5. 查询待下载的视频
    6. 下载视频并更新状态
    """
    # 创建控制台对象，用于彩色输出
    console = ColorfulConsole()
    
    # 从配置文件加载设置
    config_path = Path("notion_config.json")
    if not config_path.exists():
        # 配置文件不存在时输出错误信息
        console.error(f"配置文件 {config_path} 不存在！")
        console.info("请创建配置文件，包含以下内容：")
        console.info("""
{
    "notion_token": "你的Notion API令牌",
    "database_id": "你的数据库ID",
    "download_dir": "Download/Notion"
}
        """)
        return
    
    try:
        # 读取并解析配置文件
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            
        # 获取配置项
        notion_token = config.get("notion_token", "")  # Notion API令牌
        database_id = config.get("database_id", "")  # 数据库ID
        download_dir = config.get("download_dir", "Download/Notion")  # 下载目录
        
        # 输出配置信息
        console.info(f"已从配置文件 {config_path} 加载设置")
        console.info(f"数据库ID: {database_id}")
        console.info(f"下载目录: {download_dir}")
        
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        # 处理配置文件读取错误
        console.error(f"读取配置文件失败: {str(e)}")
        return
    
    # 检查必要的配置项
    if not notion_token:
        console.error("错误: 未设置Notion API令牌")
        return
    
    if not database_id:
        console.error("错误: 未设置Notion数据库ID")
        return
    
    # 创建下载目录（如果不存在）
    os.makedirs(download_dir, exist_ok=True)
    
    try:
        # 创建Notion管理器
        notion = NotionManager(notion_token, database_id, console)
        
        # 第一步：查询需要获取视频ID的数据
        # 过滤条件：抖音id为空且抖音url不为空
        filter_params = {
            "and": [
                {
                    "property": "抖音id",
                    "rich_text": {
                        "is_empty": True
                    }
                },
                {
                    "property": "抖音url",
                    "url": {
                        "is_not_empty": True
                    }
                }
            ]
        }
        
        # 执行查询
        pages_need_id = await notion.query_database(filter_params)
        
        if pages_need_id:
            console.info(f"找到 {len(pages_need_id)} 个需要获取视频ID的数据")
            
            # 获取并更新视频ID
            for page in pages_need_id:
                url = notion.get_url_from_page(page)
                if not url:
                    continue
                    
                console.info(f"正在获取视频ID: {url}")
                video_id = await notion.get_video_id(url)
                
                if video_id:
                    if await notion.update_video_id(page["id"], video_id):
                        console.info(f"已更新视频ID: {video_id}")
                    else:
                        console.error(f"更新视频ID失败")
        else:
            console.info("没有找到需要获取视频ID的数据")
        
        # 第二步：查询待下载的视频
        # 过滤条件：抖音状态 = 待下载
        filter_params = {
            "property": "抖音状态",
            "status": {
                "equals": "待下载"
            }
        }
        
        # 执行查询
        pages = await notion.query_database(filter_params)
        
        # 检查查询结果
        if not pages:
            console.info("没有找到待下载的视频")
            return
            
        console.info(f"找到 {len(pages)} 个待下载的视频")
        
        # 下载视频并更新状态
        for page in pages:
            await download_and_update(notion, page, download_dir, console)
            
    except Exception as e:
        # 处理运行过程中的异常
        console.error(f"运行下载器时出错: {str(e)}")
        import traceback
        console.error(traceback.format_exc())


# 程序入口点
if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
