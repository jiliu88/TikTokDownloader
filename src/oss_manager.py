"""
文件: oss_manager.py
作用: 阿里云OSS管理器，负责处理视频文件的上传和获取链接
"""

import os
import json
from pathlib import Path
import oss2  # 阿里云OSS SDK
from typing import Optional, Dict, Tuple

from .tools import ColorfulConsole  # 导入彩色控制台输出工具

class OSSManager:
    """
    阿里云OSS管理器
    
    负责处理视频文件的上传和获取公开访问链接
    """
    
    def __init__(self, config: Dict, console: Optional[ColorfulConsole] = None):
        """
        初始化OSS管理器
        
        Args:
            config: OSS配置信息字典
            console: 控制台对象，用于输出日志
        """
        self.console = console or ColorfulConsole()
        self.config = config["oss"]  # 直接使用传入的配置
        self.auth = oss2.Auth(self.config["access_key_id"], self.config["access_key_secret"])
        self.bucket = oss2.Bucket(self.auth, self.config["endpoint"], self.config["bucket_name"])
        
    async def upload_video(self, video_path: str, video_id: str) -> Tuple[bool, str]:
        """
        上传视频文件到OSS
        
        Args:
            video_path: 视频文件路径
            video_id: 视频ID，用作OSS中的文件名
            
        Returns:
            (是否成功, 文件URL或错误信息)
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(video_path):
                return False, f"视频文件不存在: {video_path}"
                
            # 获取文件扩展名
            _, ext = os.path.splitext(video_path)
            # 构建OSS中的文件名
            oss_key = f"videos/{video_id}{ext}"
            
            # 上传文件
            self.console.info(f"正在上传视频到OSS: {oss_key}")
            with open(video_path, "rb") as f:
                self.bucket.put_object(oss_key, f)
                
            # 使用配置中的base_url生成访问链接
            url = f"{self.config['base_url']}/{oss_key}"
            
            self.console.info(f"视频上传成功: {url}")
            return True, url
            
        except Exception as e:
            error_msg = f"上传视频到OSS失败: {str(e)}"
            self.console.error(error_msg)
            return False, error_msg 