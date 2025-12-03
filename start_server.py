#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
船舶可视化后端服务启动脚本
提供更健壮的服务启动和错误处理
"""

import os
import sys
import logging
import time
from datetime import datetime

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('ship-visualizer-server')

def start_server():
    """启动Flask后端服务"""
    try:
        logger.info("=== 开始启动船舶可视化后端服务 ===")
        logger.info(f"当前工作目录: {os.getcwd()}")
        logger.info(f"Python版本: {sys.version}")
        
        # 导入Flask应用
        logger.info("正在导入Flask应用...")
        from app import app
        
        # 配置应用 - 关闭调试模式以提高稳定性
        app.config['DEBUG'] = False
        
        # 显示配置信息
        logger.info(f"服务配置: DEBUG={app.config['DEBUG']}")
        logger.info(f"上传目录: {app.config.get('UPLOAD_FOLDER', '未设置')}")
        
        # 启动服务
        logger.info("=== 服务启动配置完成，正在启动服务器 ===")
        logger.info("服务地址: http://0.0.0.0:5000")
        logger.info("调试模式: 已禁用")
        logger.info("=== 按 Ctrl+C 停止服务 ===  ")
        
        # 启动Flask服务，关闭调试模式并禁用自动重载以提高稳定性
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
        
    except ImportError as e:
        logger.error(f"导入错误: {str(e)}")
        logger.error("请检查是否已安装所有依赖包")
        logger.error("推荐执行: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("=== 服务已停止 ===")

if __name__ == '__main__':
    try:
        start_server()
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在停止服务...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"发生致命错误: {str(e)}", exc_info=True)
        sys.exit(1)