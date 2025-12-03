#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版船舶轨迹可视化后端服务
专注于文件读取和基本数据处理功能
"""

import os
import json
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS  # 添加CORS支持
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('simple-server')

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 启用CORS，允许跨域请求

# 配置
app.config['DEBUG'] = True

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    logger.info("接收到健康检查请求")
    return jsonify({
        "status": "healthy",
        "message": "简化版船舶可视化后端服务运行正常",
        "version": "1.0.0",
        "timestamp": pd.Timestamp.now().isoformat()
    })

def extract_ship_id(name):
    """从船名提取船舶ID"""
    if isinstance(name, str):
        # 尝试提取数字ID
        import re
        digits = re.findall(r'\d+', name)
        if digits:
            return f"SHIP_{digits[0]}"
        # 否则返回名称的前10个字符
        return f"SHIP_{name[:10].upper().replace(' ', '_')}"
    return f"SHIP_{hash(str(name)) % 10000}"

def process_csv_data(df):
    """处理CSV数据生成轨迹信息"""
    try:
        logger.info(f"开始处理CSV数据，共{len(df)}行")
        
        # 确保数据有必要的列
        required_columns = ['Latitude', 'Longitude', 'MMSI', 'BaseDateTime']
        available_columns = [col for col in required_columns if col in df.columns]
        
        if len(available_columns) < 2:
            raise ValueError(f"CSV文件缺少必要的坐标列，可用列: {available_columns}")
        
        # 清理数据
        df = df.dropna(subset=['Latitude', 'Longitude'])
        df = df[df['Latitude'].between(-90, 90) & df['Longitude'].between(-180, 180)]
        
        if len(df) == 0:
            raise ValueError("没有有效的坐标数据")
        
        # 生成轨迹数据
        trajectories = []
        
        # 如果有MMSI列，按船舶分组
        if 'MMSI' in df.columns:
            for mmsi, group in df.groupby('MMSI'):
                ship_id = extract_ship_id(mmsi)
                points = []
                for _, row in group.iterrows():
                    point = {
                        'lat': float(row['Latitude']),
                        'lng': float(row['Longitude']),
                        'time': str(row.get('BaseDateTime', pd.Timestamp.now()))
                    }
                    points.append(point)
                
                if len(points) > 1:  # 只有多点才能形成轨迹
                    trajectories.append({
                        'id': ship_id,
                        'name': f"Ship {mmsi}",
                        'points': points[:1000],  # 限制点数
                        'point_count': len(points)
                    })
        else:
            # 否则作为单条轨迹处理
            points = []
            for _, row in df.iterrows():
                point = {
                    'lat': float(row['Latitude']),
                    'lng': float(row['Longitude']),
                    'time': str(row.get('BaseDateTime', pd.Timestamp.now()))
                }
                points.append(point)
            
            trajectories.append({
                'id': 'SINGLE_TRACK',
                'name': 'Single Ship Track',
                'points': points[:1000],
                'point_count': len(points)
            })
        
        statistics = {
            'total_records': len(df),
            'ship_count': len(trajectories),
            'total_points': sum(t['point_count'] for t in trajectories)
        }
        
        logger.info(f"数据处理完成，生成{len(trajectories)}条轨迹")
        return trajectories, statistics
        
    except Exception as e:
        logger.error(f"处理CSV数据时出错: {str(e)}")
        raise

@app.route('/api/read-file', methods=['POST'])
def read_file():
    """直接读取CSV文件"""
    try:
        logger.info("接收到读取文件请求")
        
        # 检查请求格式
        if not request.is_json:
            logger.error("请求不是JSON格式")
            return jsonify({"error": "请求必须是JSON格式"}), 400
            
        # 获取文件路径
        data = request.json
        file_path = data.get('file_path', '')
        
        logger.info(f"请求读取文件: {file_path}")
        
        # 验证文件路径
        if not file_path:
            return jsonify({"error": "请提供文件路径"}), 400
            
        if not file_path.endswith(('.csv', '.txt')):
            return jsonify({"error": "只支持CSV和TXT文件"}), 400
            
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({"error": f"文件不存在: {file_path}"}), 404
            
        # 检查文件是否可读
        if not os.access(file_path, os.R_OK):
            return jsonify({"error": f"无权限读取文件: {file_path}"}), 403
        
        # 尝试多种编码读取文件
        encodings = ['utf-8', 'gbk', 'latin-1', 'utf-16']
        df = None
        used_encoding = None
        
        for encoding in encodings:
            try:
                logger.info(f"尝试用{encoding}编码读取文件")
                df = pd.read_csv(file_path, encoding=encoding)
                used_encoding = encoding
                logger.info(f"成功以{encoding}编码读取文件，共{len(df)}行")
                break
            except UnicodeDecodeError:
                logger.warning(f"{encoding}编码读取失败，尝试下一种")
                continue
            except Exception as e:
                logger.warning(f"读取文件时出错({encoding}): {str(e)}")
                continue
        
        if df is None:
            return jsonify({"error": "无法解析CSV文件，尝试了多种编码"}), 400
        
        # 处理数据
        trajectories, statistics = process_csv_data(df)
        
        # 返回结果
        return jsonify({
            "trajectories": trajectories,
            "statistics": statistics,
            "file_info": {
                "path": file_path,
                "encoding": used_encoding,
                "rows": len(df),
                "columns": list(df.columns)
            }
        })
        
    except Exception as e:
        logger.error(f"读取文件错误: {str(e)}", exc_info=True)
        return jsonify({"error": f"读取文件失败: {str(e)}"}), 500

if __name__ == '__main__':
    print("=== 启动简化版船舶可视化后端服务 ===")
    print(f"服务地址: http://0.0.0.0:5001")
    print(f"调试模式: {app.config['DEBUG']}")
    print("API端点:")
    print("  GET  /api/health       - 健康检查")
    print("  POST /api/read-file    - 读取CSV文件")
    print("=== 按 Ctrl+C 停止服务 ===")
    
    # 启动服务，使用不同的端口避免冲突
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)