"""
文件: notion_downloader_main.py
作用: Notion抖音视频下载器的入口脚本
"""

import asyncio
import os
import json
import argparse
from pathlib import Path
import httpx

from src.notion_downloader import NotionDownloader
from src.tools import ColorfulConsole


async def main():
    """
    主函数
    """
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="从Notion下载抖音视频")
    parser.add_argument("--token", help="Notion API令牌")
    parser.add_argument("--database", help="Notion数据库ID")
    parser.add_argument("--config", help="配置文件路径", default="notion_config.json")
    parser.add_argument("--download-dir", help="下载目录", default="Download/Notion")
    parser.add_argument("--upload", help="是否将下载的视频上传回Notion", action="store_true")
    parser.add_argument("--url", help="直接下载指定的抖音URL")
    
    args = parser.parse_args()
    
    console = ColorfulConsole()
    
    # 获取Notion API令牌和数据库ID
    notion_token = args.token or os.environ.get("NOTION_TOKEN", "")
    database_id = args.database or os.environ.get("NOTION_DATABASE_ID", "")
    download_dir = args.download_dir or os.environ.get("NOTION_DOWNLOAD_DIR", "Download/Notion")
    upload_to_notion = args.upload
    
    # 如果命令行参数和环境变量都没有提供，尝试从配置文件加载
    if not notion_token or not database_id:
        config_path = Path(args.config)
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    notion_token = notion_token or config.get("notion_token", "")
                    database_id = database_id or config.get("database_id", "")
                    download_dir = download_dir or config.get("download_dir", "Download/Notion")
                    # 如果配置文件中有upload_to_notion设置，则使用它
                    if "upload_to_notion" in config and not args.upload:
                        upload_to_notion = config.get("upload_to_notion", False)
                    console.info(f"已从配置文件 {config_path} 加载设置")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                console.error(f"读取配置文件失败: {str(e)}")
        else:
            console.warning(f"配置文件 {config_path} 不存在")
    
    # 检查是否有必要的配置
    if not notion_token:
        console.error("错误: 未设置Notion API令牌")
        console.info("请通过以下方式之一设置Notion API令牌:")
        console.info("1. 命令行参数: --token YOUR_TOKEN")
        console.info("2. 环境变量: NOTION_TOKEN=YOUR_TOKEN")
        console.info("3. 配置文件: notion_config.json")
        return
    
    if not database_id and not args.url:
        console.error("错误: 未设置Notion数据库ID或直接下载URL")
        console.info("请通过以下方式之一设置Notion数据库ID:")
        console.info("1. 命令行参数: --database YOUR_DATABASE_ID")
        console.info("2. 环境变量: NOTION_DATABASE_ID=YOUR_DATABASE_ID")
        console.info("3. 配置文件: notion_config.json")
        console.info("或者使用 --url 参数直接指定要下载的抖音URL")
        return
    
    # 创建下载目录
    os.makedirs(download_dir, exist_ok=True)
    
    # 运行下载器
    console.info(f"使用数据库ID: {database_id}")
    console.info(f"下载目录: {download_dir}")
    console.info(f"是否上传到Notion: {'是' if upload_to_notion else '否'}")
    
    try:
        # 创建NotionDownloader实例
        downloader = NotionDownloader(notion_token, database_id, download_dir)
        
        # 如果指定了直接下载URL，则直接下载
        if args.url:
            console.info(f"直接下载URL: {args.url}")
            video_path = await downloader.download_video(args.url)
            if video_path:
                console.print(f"视频下载成功: {video_path}")
            else:
                console.error(f"视频下载失败: {args.url}")
            return
        
        # 否则，查询Notion数据库并下载视频
        # 使用传统的HTTP请求方式查询Notion数据库
        headers = {
            "Authorization": f"Bearer {notion_token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        # 查询待下载的视频
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        payload = {
            "filter": {
                "property": "抖音状态",
                "status": {
                    "equals": "待下载"
                }
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    console.error(f"查询Notion数据库失败: {response.text}")
                    return
                    
                data = response.json()
                pages = data.get("results", [])
        except Exception as e:
            console.error(f"查询Notion数据库时出错: {str(e)}")
            import traceback
            console.error(traceback.format_exc())
            return
        
        if not pages:
            console.info("没有找到待下载的视频")
            return
            
        console.info(f"找到 {len(pages)} 个待下载的视频")
        
        # 下载视频
        for page in pages:
            # 获取视频URL
            url = downloader.get_url_from_page(page)
            if not url:
                console.info(f"页面 {page['id']} 没有找到视频URL，跳过")
                continue
            
            console.info(f"开始下载视频: {url}")
            
            # 下载视频
            video_path = await downloader.download_video(url)
            
            if video_path:
                console.print(f"视频下载成功: {video_path}")
                
                # 更新Notion数据库中的状态
                page_id = page["id"]
                
                # 获取状态属性类型
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
                                "name": "已下载"
                            }
                        }
                    }
                elif status_type == "rich_text":
                    properties = {
                        "抖音状态": {
                            "rich_text": [
                                {
                                    "text": {
                                        "content": "已下载"
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
                                        "content": "已下载"
                                    }
                                }
                            ]
                        }
                    }
                elif status_type == "status":
                    properties = {
                        "抖音状态": {
                            "status": {
                                "name": "已下载"
                            }
                        }
                    }
                
                # 更新页面
                update_url = f"https://api.notion.com/v1/pages/{page_id}"
                payload = {
                    "properties": properties
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.patch(update_url, headers=headers, json=payload)
                    
                    if response.status_code != 200:
                        console.error(f"更新Notion页面失败: {response.text}")
                    else:
                        console.info(f"已更新页面状态为: 已下载")
            else:
                console.error(f"视频下载失败: {url}")
                
                # 更新Notion数据库中的状态为"下载失败"
                page_id = page["id"]
                
                # 获取状态属性类型
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
                                "name": "下载失败"
                            }
                        }
                    }
                elif status_type == "rich_text":
                    properties = {
                        "抖音状态": {
                            "rich_text": [
                                {
                                    "text": {
                                        "content": "下载失败"
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
                                        "content": "下载失败"
                                    }
                                }
                            ]
                        }
                    }
                elif status_type == "status":
                    properties = {
                        "抖音状态": {
                            "status": {
                                "name": "下载失败"
                            }
                        }
                    }
                
                # 更新页面
                update_url = f"https://api.notion.com/v1/pages/{page_id}"
                payload = {
                    "properties": properties
                }
                
                async with httpx.AsyncClient() as client:
                    response = await client.patch(update_url, headers=headers, json=payload)
                    
                    if response.status_code != 200:
                        console.error(f"更新Notion页面失败: {response.text}")
                    else:
                        console.info(f"已更新页面状态为: 下载失败")
    except Exception as e:
        console.error(f"运行下载器时出错: {str(e)}")
        import traceback
        console.error(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main()) 
