from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
from datetime import datetime
import traceback

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置文件上传
UPLOAD_FOLDER = 'data/uploads'
PROCESSED_FOLDER = 'data/processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB限制

# 存储上传的文件信息
uploaded_files = []

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传CSV文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有文件部分'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        if file and file.filename.endswith('.csv'):
            # 生成唯一文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # 保存文件
            file.save(filepath)
            
            # 记录文件信息
            file_info = {
                'filename': filename,
                'original_name': file.filename,
                'upload_time': timestamp,
                'filepath': filepath
            }
            uploaded_files.append(file_info)
            
            return jsonify({
                'message': '文件上传成功',
                'filename': filename,
                'file_info': file_info
            }), 200
        else:
            return jsonify({'error': '只支持CSV文件'}), 400
            
    except Exception as e:
        print(f"上传错误: {str(e)}")
        return jsonify({'error': f'上传失败: {str(e)}'}), 500

@app.route('/api/files', methods=['GET'])
def get_files():
    """获取已上传的文件列表"""
    return jsonify({
        'files': uploaded_files,
        'count': len(uploaded_files)
    })

@app.route('/api/data/<filename>', methods=['GET'])
def get_csv_data(filename):
    """读取CSV文件数据"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        
        # 读取CSV文件
        # ========== 数据处理位置 ==========
        # 这里可以添加数据预处理逻辑，比如：
        # 1. 数据清洗
        # 2. 格式转换
        # 3. 异常值处理
        # ================================
        
        df = pd.read_csv(filepath)
        
        # 返回前100行数据（避免数据过大）
        data = df.head(100).to_dict('records')
        
        # 返回数据统计信息
        stats = {
            'total_rows': len(df),
            'columns': df.columns.tolist(),
            'data_types': df.dtypes.astype(str).to_dict()
        }
        
        return jsonify({
            'filename': filename,
            'data': data,
            'stats': stats,
            'message': '数据读取成功'
        })
        
    except Exception as e:
        print(f"读取CSV错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': f'读取CSV文件失败: {str(e)}'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({'status': 'healthy', 'message': '后端服务运行正常'})

if __name__ == '__main__':
    print("启动船舶可视化后端服务...")
    print(f"上传文件目录: {app.config['UPLOAD_FOLDER']}")
    app.run(host='0.0.0.0', port=5000, debug=True)