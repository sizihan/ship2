#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试文件上传和数据处理功能的脚本
"""

import http.client
import mimetypes
import os
import json
import urllib.parse

# 测试文件上传
def upload_file(file_path):
    if not os.path.exists(file_path):
        print(f"测试文件 {file_path} 不存在")
        return False
    
    # 检查文件类型
    file_ext = os.path.splitext(file_path)[1].lower()
    file_type = "Excel文件" if file_ext in ['.xlsx', '.xls'] else "CSV文件"
    print(f"开始上传{file_type}: {file_path}")
    
    # 准备multipart/form-data请求
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    file_name = os.path.basename(file_path)
    content_type = mimetypes.guess_type(file_name)[0] or 'application/octet-stream'
    
    # 读取文件内容
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    # 构建请求体
    body = (f'--{boundary}\r\n' +
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n' +
            f'Content-Type: {content_type}\r\n\r\n').encode()
    body += file_content + f'\r\n--{boundary}--\r\n'.encode()
    
    # 发送请求
    try:
        conn = http.client.HTTPConnection('localhost', 5000)
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
        }
        conn.request('POST', '/api/upload', body, headers)
        response = conn.getresponse()
        
        print(f"上传状态码: {response.status}")
        response_data = response.read().decode()
        print(f"上传响应: {response_data}")
        
        conn.close()
        return response_data
    except Exception as e:
        print(f"上传过程中出错: {str(e)}")
        return False

# 测试GET请求
def send_get_request(endpoint):
    try:
        conn = http.client.HTTPConnection('localhost', 5000)
        conn.request('GET', endpoint)
        response = conn.getresponse()
        
        print(f"状态码: {response.status}")
        response_data = response.read().decode()
        print(f"响应: {response_data}")
        
        conn.close()
        return response_data
    except Exception as e:
        print(f"请求过程中出错: {str(e)}")
        return None

def main():
    """
    主测试流程
    """
    print("===== 船舶可视化后端服务测试工具 =====")
    print("服务地址: http://localhost:5000")
    print("支持的文件格式: CSV, XLSX, XLS")
    
    # 提示用户输入文件路径
    print("\n请输入要测试的文件路径（CSV或Excel）")
    print("或者直接按回车使用默认测试文件 'test_ship.csv'")
    user_input = input("文件路径: ").strip()
    
    file_path = user_input if user_input else 'test_ship.csv'
    
    # 上传文件
    response_data = upload_file(file_path)
    if response_data:
        # 解析上传响应，获取实际文件名
        try:
            upload_response = json.loads(response_data)
            actual_filename = upload_response.get('filename') or upload_response.get('file_info', {}).get('filename')
            
            if actual_filename:
                print(f"\n获取到实际文件名: {actual_filename}")
                
                # 测试获取文件列表
                print("\n获取文件列表:")
                send_get_request('/api/files')
                
                # 测试获取上传的文件数据 - 使用实际文件名
                print("\n获取上传的文件数据:")
                send_get_request(f'/api/data/{actual_filename}')
            else:
                print("\n无法从响应中获取文件名")
                # 仍然尝试获取文件列表
                print("\n获取文件列表:")
                send_get_request('/api/files')
                
        except Exception as e:
            print(f"解析响应时出错: {str(e)}")
            # 仍然尝试获取文件列表
            print("\n获取文件列表:")
            send_get_request('/api/files')


if __name__ == '__main__':
    main()