# Notion 抖音视频下载器

这个模块允许你通过 Notion API 获取表格数据，下载抖音视频，并将下载状态更新回 Notion 表格。

## 功能特点

- 从 Notion 数据库中读取待下载的抖音视频链接
- 自动下载抖音视频
- 将下载状态和文件路径更新回 Notion 数据库
- 支持命令行参数、环境变量和配置文件三种方式配置

## 前提条件

1. 已创建 Notion 集成（Integration）并获取 API 令牌
2. 已创建 Notion 数据库，并与集成共享
3. 数据库中包含以下属性：
   - `URL`：存储抖音视频链接的属性（URL 或文本类型）
   - `Status`：表示下载状态的属性（选择类型，包含"待下载"、"下载中"、"已下载"、"下载失败"选项）
   - `File`：存储下载文件路径的属性（文本类型）

## 安装

1. 确保已安装 TikTokDownloader 的所有依赖
2. 复制 `notion_config.json.template` 为 `notion_config.json` 并填写你的 Notion API 令牌和数据库 ID

## 配置

你可以通过以下三种方式之一配置 Notion API 令牌和数据库 ID：

### 1. 配置文件

创建 `notion_config.json` 文件：

```json
{
    "notion_token": "your_notion_integration_token_here",
    "database_id": "your_notion_database_id_here",
    "download_dir": "Download/Notion"
}
```

### 2. 环境变量

设置以下环境变量：

```bash
export NOTION_TOKEN="your_notion_integration_token_here"
export NOTION_DATABASE_ID="your_notion_database_id_here"
export NOTION_DOWNLOAD_DIR="Download/Notion"  # 可选
```

### 3. 命令行参数

运行时指定参数：

```bash
python notion_downloader_main.py --token "your_token" --database "your_database_id" --download-dir "Download/Notion"
```

## 使用方法

1. 在 Notion 数据库中添加待下载的抖音视频链接，并将状态设置为"待下载"
2. 运行下载器：

```bash
python notion_downloader_main.py
```

3. 下载器会自动处理所有标记为"待下载"的视频，并更新其状态

## Notion 数据库设置指南

1. 在 Notion 中创建一个新的数据库
2. 添加以下属性：
   - `URL`（URL 或文本类型）：用于存储抖音视频链接
   - `Status`（选择类型）：添加以下选项：
     - 待下载
     - 下载中
     - 已下载
     - 下载失败
   - `File`（文本类型）：用于存储下载文件的路径

3. 创建 Notion 集成：
   - 访问 [Notion Developers](https://www.notion.so/my-integrations)
   - 点击"New integration"
   - 填写集成名称和工作区
   - 获取 API 令牌

4. 将数据库与集成共享：
   - 打开你的数据库
   - 点击右上角的"Share"按钮
   - 在搜索框中输入你的集成名称
   - 选择集成并点击"Invite"

5. 获取数据库 ID：
   - 打开你的数据库
   - 从 URL 中复制数据库 ID（格式为：https://www.notion.so/xxx?v=yyy，其中 xxx 就是数据库 ID）

## 注意事项

- 确保你的 Notion 集成有足够的权限访问数据库
- 下载大量视频可能需要较长时间，请耐心等待
- 如果下载失败，可以手动将状态重新设置为"待下载"再次尝试 