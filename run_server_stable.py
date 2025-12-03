#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
船舶可视化后端服务稳定启动脚本
确保服务能够持续运行
"""

import os
import sys
import logging
import time
from wsgiref.simple_server import make_server
import werkzeug.serving

# 配置详细日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('ship-visualizer-server-stable')

def run_stable_server():
    """使用wsgiref服务器稳定运行Flask应用"""
    try:
        logger.info("=== 开始启动船舶可视化后端服务 (稳定模式) ===")
        logger.info(f"当前工作目录: {os.getcwd()}")
        logger.info(f"Python版本: {sys.version}")
        
        # 导入Flask应用
        logger.info("正在导入Flask应用...")
        from app import app
        
        # 配置应用
        app.config['DEBUG'] = False
        
        # 显示配置信息
        logger.info(f"服务配置: DEBUG={app.config['DEBUG']}")
        logger.info(f"上传目录: {app.config.get('UPLOAD_FOLDER', '未设置')}")
        
        # 创建WSGI服务器
        logger.info("=== 服务启动配置完成，正在启动WSGI服务器 ===")
        logger.info("服务地址: http://0.0.0.0:5000")
        logger.info("=== 按 Ctrl+C 停止服务 ===  ")
        
        # 使用wsgiref简单服务器
        server = make_server('0.0.0.0', 5000, app)
        server.serve_forever()
        
    except ImportError as e:
        logger.error(f"导入错误: {str(e)}")
        logger.error("请检查是否已安装所有依赖包")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在停止服务...")
    except Exception as e:
        logger.error(f"服务运行出错: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("=== 服务已停止 ===")

if __name__ == '__main__':
    run_stable_server()