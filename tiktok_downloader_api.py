#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TikTok下载器API

提供可以在其他Python代码中调用的函数，用于下载单个视频。
"""

from asyncio import run
from pathlib import Path
from typing import Optional, List, Dict, Any, Union


async def _download_video(url: str, is_tiktok: bool = False, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    下载单个视频的异步实现
    
    Args:
        url: 视频链接
        is_tiktok: 是否为TikTok视频，默认为False（抖音视频）
        output_dir: 输出目录，默认为None（使用配置文件中的设置）
        
    Returns:
        包含下载结果的字典
    """
    from src.application import TikTokDownloader
    from src.application.main_complete import TikTok
    
    result = {
        "success": False,
        "message": "",
        "video_path": None,
        "cover_path": None,
        "video_info": {}
    }
    
    try:
        async with TikTokDownloader() as downloader:
            # 初始化
            downloader.project_info()
            downloader.check_config()
            await downloader.check_settings(False)
            
            # 如果指定了输出目录，则修改配置
            if output_dir:
                downloader.parameter.root = Path(output_dir)
            
            # 创建TikTok实例
            tiktok = TikTok(
                downloader.parameter,
                downloader.database,
            )
            
            # 创建记录器
            root, params, logger = tiktok.record.run(downloader.parameter)
            
            # 下载视频
            async with logger(root, console=downloader.console, **params) as record:
                # 提取视频ID
                link_obj = tiktok.links_tiktok if is_tiktok else tiktok.links
                ids = await link_obj.run(url)
                
                if not any(ids):
                    result["message"] = f"提取作品ID失败: {url}"
                    return result
                
                # 处理视频
                preview_image = await tiktok._handle_detail(ids, is_tiktok, record)
                
                # 查找下载的视频文件
                download_dir = downloader.parameter.root
                video_files = list(download_dir.glob("**/*.mp4"))
                if not video_files:
                    # 尝试查找其他视频格式
                    video_files = list(download_dir.glob("**/*.mp4")) + \
                                list(download_dir.glob("**/*.webm")) + \
                                list(download_dir.glob("**/*.mov"))
                
                if video_files:
                    # 按修改时间排序，获取最新的文件
                    video_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    result["video_path"] = str(video_files[0])
                    result["success"] = True
                    result["message"] = "下载成功"
                    
                    # 如果有封面图，也返回
                    if preview_image:
                        result["cover_path"] = preview_image
                else:
                    result["message"] = "下载完成但未找到视频文件"
                
                return result
    except Exception as e:
        import traceback
        result["message"] = f"下载过程中发生错误: {str(e)}\n{traceback.format_exc()}"
        return result


def download_video(url: str, is_tiktok: bool = False, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    下载单个视频
    
    Args:
        url: 视频链接
        is_tiktok: 是否为TikTok视频，默认为False（抖音视频）
        output_dir: 输出目录，默认为None（使用配置文件中的设置）
        
    Returns:
        包含下载结果的字典
    """
    return run(_download_video(url, is_tiktok, output_dir))


def download_douyin_video(url: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    下载抖音视频
    
    Args:
        url: 抖音视频链接
        output_dir: 输出目录，默认为None（使用配置文件中的设置）
        
    Returns:
        包含下载结果的字典
    """
    return download_video(url, False, output_dir)


def download_tiktok_video(url: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    下载TikTok视频
    
    Args:
        url: TikTok视频链接
        output_dir: 输出目录，默认为None（使用配置文件中的设置）
        
    Returns:
        包含下载结果的字典
    """
    return download_video(url, True, output_dir)


# 使用示例
if __name__ == "__main__":
    # 下载抖音视频
    result = download_douyin_video("https://v.douyin.com/sVlvRD0ljNM/")
    print(f"下载结果: {result['success']}")
    print(f"消息: {result['message']}")
    print(f"视频路径: {result['video_path']}")
    
    # 下载TikTok视频
    # result = download_tiktok_video("https://www.tiktok.com/@用户名/video/视频ID")
    # print(f"下载结果: {result['success']}")
    # print(f"消息: {result['message']}")
    # print(f"视频路径: {result['video_path']}") 