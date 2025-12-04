from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import os
import re
from datetime import datetime
import traceback
import math
from dotenv import load_dotenv
import logging

# 配置详细的日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 加载环境变量
load_dotenv()

app = Flask(__name__)

# 配置 CORS，明确允许 Vercel 域名和其他来源
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://ship-steel.vercel.app",
            "https://*.vercel.app",
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": False
    }
})

# 配置文件上传 - 使用绝对路径避免相对路径问题
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'data/uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'data/processed')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB限制
app.config['DEBUG'] = os.environ.get('DEBUG', 'False').lower() == 'true'

# 存储上传的文件信息
# 注意：这是内存存储，服务器重启后数据会丢失
# 生产环境建议使用数据库存储
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
        
        # 安全文件名检查 - 放宽限制，允许更多字符（包括中文）
        # 只禁止明显的路径分隔符和特殊字符
        if re.search(r'[\\/:*?"<>|]', file.filename):
            return jsonify({'error': '文件名包含非法字符（不能包含 \\/:*?"<>|）'}), 400
        
        # 支持CSV、Excel和TXT文件上传
        if file and file.filename.lower().endswith(('.csv', '.xlsx', '.xls', '.txt')):
            # 在保存新文件之前，删除uploads目录中的所有旧文件
            try:
                upload_folder = app.config['UPLOAD_FOLDER']
                if os.path.exists(upload_folder):
                    deleted_count = 0
                    for old_file in os.listdir(upload_folder):
                        old_file_path = os.path.join(upload_folder, old_file)
                        try:
                            if os.path.isfile(old_file_path):
                                os.remove(old_file_path)
                                deleted_count += 1
                                app.logger.info(f"已删除旧文件: {old_file}")
                        except Exception as e:
                            app.logger.warning(f"删除旧文件失败 {old_file}: {str(e)}")
                    
                    # 清空已上传文件列表
                    uploaded_files.clear()
                    app.logger.info(f"已清理 {deleted_count} 个旧文件")
            except Exception as e:
                app.logger.warning(f"清理旧文件时出错: {str(e)}")
                # 继续执行，不阻止新文件上传
            
            # 生成唯一文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # 过滤文件名，移除可能的路径分隔符
            safe_filename = re.sub(r'[\\/:*?"<>|]', '_', file.filename)
            filename = f"{timestamp}_{safe_filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # 检查目标目录是否可写
            if not os.access(app.config['UPLOAD_FOLDER'], os.W_OK):
                return jsonify({'error': '文件目录无写入权限'}), 500
            
            # 保存文件
            file.save(filepath)
            
            # 记录文件信息
            file_info = {
                'filename': filename,
                'original_name': file.filename,
                'upload_time': timestamp,
                'filepath': filepath,
                'size': os.path.getsize(filepath),
                'upload_datetime': datetime.now().isoformat()
            }
            uploaded_files.append(file_info)
            
            return jsonify({
                'message': '文件上传成功',
                'filename': filename,
                'file_info': file_info
            }), 200
        else:
            return jsonify({'error': '只支持CSV、Excel和TXT文件(.csv, .xlsx, .xls, .txt)'}), 400
            
    except Exception as e:
            app.logger.error(f"上传错误: {str(e)}")
            app.logger.debug(traceback.format_exc())
            # 不向用户暴露详细错误信息
            return jsonify({'error': '上传过程中发生错误'}), 500

@app.route('/api/files', methods=['GET'])
def get_files():
    """获取已上传的文件列表"""
    return jsonify({
        'files': uploaded_files,
        'count': len(uploaded_files)
    })

@app.route('/api/data/<filename>', methods=['GET'])
def get_csv_data(filename):
    """读取CSV文件数据并处理轨迹信息"""
    try:
        # 安全检查，防止路径遍历攻击
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': '文件名不合法'}), 400
        
        # 正常处理所有上传的文件
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在', 'filepath': filepath}), 404
        
        # 添加文件修改时间到日志，用于调试实时更新
        file_mtime = os.path.getmtime(filepath)
        file_mtime_str = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        app.logger.info(f"读取文件: {filename}, 最后修改时间: {file_mtime_str}")
        
        # 尝试读取文件，支持CSV和Excel格式
        df = None
        
        # 检查文件扩展名
        file_ext = os.path.splitext(filename)[1].lower()
        
        try:
            # 如果是Excel文件，使用read_excel读取
            if file_ext in ['.xlsx', '.xls']:
                print(f"尝试读取Excel文件: {filepath}")
                df = pd.read_excel(filepath)
                print("成功读取Excel文件")
            # 对于CSV和TXT文件，作为CSV格式读取，支持多种编码格式
            else:
                encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1', 'cp1252', 
                         'utf-16', 'utf-16-le', 'utf-16-be', 'cp936', 'cp437']
                
                for encoding in encodings:
                    try:
                        print(f"尝试使用 {encoding} 编码读取文件: {filepath}")
                        df = pd.read_csv(filepath, encoding=encoding)
                        print(f"成功使用 {encoding} 编码读取文件")
                        break
                    except UnicodeDecodeError:
                        print(f"{encoding} 编码解析失败，尝试下一种编码")
                        continue
                    except Exception as e:
                        print(f"读取CSV/TXT文件时出错: {str(e)}")
                        continue
        except Exception as e:
            print(f"读取文件时发生错误: {str(e)}")
        
        if df is None:
            return jsonify({'error': '文件格式错误，无法解析', 'file_type': file_ext}), 400
        
        # ========== 数据预处理 ==========
        # 只获取指定的字段：mmsi, lon, lat, dest, vessel_type
        # 1. 转换列名到小写，方便后续处理
        df.columns = df.columns.str.lower()
        
        # 2. 识别并标准化字段
        # 识别MMSI字段（船只标识符）
        mmsi_columns = ['mmsi', 'mmsi_number', 'ship_mmsi']
        mmsi_column = None
        for col in mmsi_columns:
            if col in df.columns:
                mmsi_column = col
                break
        
        # 识别经度字段
        lon_columns = ['lon', 'longitude', 'long', 'lng']
        lon_column = None
        for col in lon_columns:
            if col in df.columns:
                lon_column = col
                break
        
        # 识别纬度字段
        lat_columns = ['lat', 'latitude', 'latitude_']
        lat_column = None
        for col in lat_columns:
            if col in df.columns:
                lat_column = col
                break
        
        # 识别目的地字段
        dest_columns = ['dest', 'destination', 'port', 'dest_port']
        dest_column = None
        for col in dest_columns:
            if col in df.columns:
                dest_column = col
                break
        
        # 识别船舶类型字段
        vessel_type_columns = ['vessel_type', 'vesseltype', 'vessel-type', 'type', 'ship_type']
        vessel_type_column = None
        for col in vessel_type_columns:
            if col in df.columns:
                vessel_type_column = col
                break
        
        # 识别时间字段
        time_columns = ['postime', 'timestamp', 'time', 'datetime', 'date', 'record_time', 'update_time', 'time_stamp']
        time_column = None
        for col in time_columns:
            if col in df.columns:
                time_column = col
                break
        
        # 识别国旗国家字段
        flag_ctry_columns = ['flag_ctry', 'flag_country', 'country', 'flag']
        flag_ctry_column = None
        for col in flag_ctry_columns:
            if col in df.columns:
                flag_ctry_column = col
                break
        
        # 构建新的DataFrame，只包含需要的字段
        new_df_data = {}
        
        # 处理MMSI字段
        if mmsi_column:
            if pd.api.types.is_numeric_dtype(df[mmsi_column]):
                new_df_data['mmsi'] = df[mmsi_column].astype(str)
            else:
                new_df_data['mmsi'] = df[mmsi_column].astype(str)
        else:
            # 如果没有mmsi字段，使用索引作为标识
            new_df_data['mmsi'] = df.index.astype(str)
        
        # 处理经度字段
        if lon_column:
            new_df_data['lon'] = pd.to_numeric(df[lon_column], errors='coerce')
        else:
            app.logger.warning("未找到经度字段")
            return jsonify({'error': 'CSV文件中未找到经度字段(lon/longitude)'}), 400
        
        # 处理纬度字段
        if lat_column:
            new_df_data['lat'] = pd.to_numeric(df[lat_column], errors='coerce')
        else:
            app.logger.warning("未找到纬度字段")
            return jsonify({'error': 'CSV文件中未找到纬度字段(lat/latitude)'}), 400
        
        # 处理目的地字段
        if dest_column:
            new_df_data['dest'] = df[dest_column].astype(str)
            # 将空值和'nan'字符串替换为空字符串
            new_df_data['dest'] = new_df_data['dest'].replace(['nan', 'None', 'null', 'NaN', 'NAN'], '')
            new_df_data['dest'] = new_df_data['dest'].fillna('')
        else:
            new_df_data['dest'] = ''
        
        # 处理船舶类型字段
        if vessel_type_column:
            new_df_data['vessel_type'] = df[vessel_type_column].astype(str)
            # 将空值和'nan'字符串替换为空字符串
            new_df_data['vessel_type'] = new_df_data['vessel_type'].replace(['nan', 'None', 'null', 'NaN', 'NAN'], '')
            new_df_data['vessel_type'] = new_df_data['vessel_type'].fillna('')
        else:
            new_df_data['vessel_type'] = ''
        
        # 处理国旗国家字段
        if flag_ctry_column:
            new_df_data['flag_ctry'] = df[flag_ctry_column].astype(str)
            # 将空值和'nan'字符串替换为空字符串
            new_df_data['flag_ctry'] = new_df_data['flag_ctry'].replace(['nan', 'None', 'null', 'NaN', 'NAN'], '')
            new_df_data['flag_ctry'] = new_df_data['flag_ctry'].fillna('')
        else:
            new_df_data['flag_ctry'] = ''
        
        # 处理时间字段(postime)
        if time_column:
            # 尝试将时间字段转换为datetime类型
            try:
                new_df_data['postime'] = pd.to_datetime(df[time_column], errors='coerce')
            except:
                new_df_data['postime'] = df[time_column].astype(str)
        else:
            # 如果没有时间字段，创建一个空的postime列
            app.logger.warning("未找到时间字段(postime/timestamp)")
            new_df_data['postime'] = pd.NaT
        
        # 创建新的DataFrame
        df = pd.DataFrame(new_df_data)
        
        # 4. 过滤无效的经纬度数据
        original_rows = len(df)
        df = df[(pd.notna(df['lon'])) & (pd.notna(df['lat']))]
        df = df[(df['lon'] >= -180) & (df['lon'] <= 180)]
        df = df[(df['lat'] >= -90) & (df['lat'] <= 90)]
        
        # 记录过滤后的行数
        filtered_rows = len(df)
        if original_rows > filtered_rows:
            app.logger.info(f"文件 {filename}: 过滤了 {original_rows - filtered_rows} 行无效经纬度数据，剩余 {filtered_rows} 行有效数据")
        
        if len(df) == 0:
            return jsonify({'error': '没有有效的经纬度数据'}), 400
        
        # 5. 按MMSI分组
        ship_groups = {}
        max_rows = 200000  # 提高单个船只轨迹点数限制到20万
        global_start_time = None
        global_end_time = None
        
        if 'mmsi' in df.columns:
            df_with_mmsi = df[pd.notna(df['mmsi'])]
            for mmsi_id, ship_data in df_with_mmsi.groupby('mmsi'):
                # 确保轨迹点按postime排序
                if 'postime' in ship_data.columns and pd.api.types.is_datetime64_any_dtype(ship_data['postime']):
                    ship_data_sorted = ship_data.sort_values('postime')
                    app.logger.info(f"船只 {mmsi_id} 已按时间排序，共 {len(ship_data_sorted)} 个点")
                    
                    # 计算该船只的时间范围，用于全局时间范围计算
                    ship_valid_times = ship_data_sorted['postime'].dropna()
                    if len(ship_valid_times) > 0:
                        ship_start_time = ship_valid_times.min()
                        ship_end_time = ship_valid_times.max()
                        
                        # 更新全局时间范围
                        if global_start_time is None or ship_start_time < global_start_time:
                            global_start_time = ship_start_time
                        if global_end_time is None or ship_end_time > global_end_time:
                            global_end_time = ship_end_time
                else:
                    ship_data_sorted = ship_data
                    if 'postime' in ship_data.columns:
                        app.logger.info(f"船只 {mmsi_id} 存在时间字段但非datetime类型，未排序")
                
                ship_data_limit = ship_data_sorted.head(max_rows)
                ship_groups[str(mmsi_id)] = {
                    'point_count': len(ship_data),
                    'returned_points': len(ship_data_limit),
                    'data': ship_data_limit.to_dict('records'),
                    'bounds': {
                        'min_lon': ship_data['lon'].min(),
                        'max_lon': ship_data['lon'].max(),
                        'min_lat': ship_data['lat'].min(),
                        'max_lat': ship_data['lat'].max()
                    },
                    'has_dest': 'dest' in ship_data.columns,
                    'has_vessel_type': 'vessel_type' in ship_data.columns,
                    'has_flag_ctry': 'flag_ctry' in ship_data.columns,
                    'has_timestamp': 'postime' in ship_data.columns,
                    'is_sorted_by_time': 'postime' in ship_data.columns and pd.api.types.is_datetime64_any_dtype(ship_data['postime'])
                }
        
        # 计算全局时间范围
        global_time_range = None
        if global_start_time is not None and global_end_time is not None:
            global_time_range = {
                'start_time': global_start_time.isoformat() if pd.notna(global_start_time) else None,
                'end_time': global_end_time.isoformat() if pd.notna(global_end_time) else None
            }
        
        # 6. 限制返回数据量，防止内存溢出和RangeError
        # 如果有postime字段且是datetime类型，按时间排序后再限制数据量
        if 'postime' in df.columns and pd.api.types.is_datetime64_any_dtype(df['postime']):
            data = df.sort_values('postime').head(5000).to_dict('records')
        else:
            data = df.head(5000).to_dict('records')  # 提高总体数据限制到5000行
        
        # 返回数据统计信息
        stats = {
            'total_rows': len(df),
            'columns': df.columns.tolist(),
            'data_types': df.dtypes.astype(str).to_dict(),
            'trajectory_stats': {
                'point_count': len(df),
                'has_valid_coordinates': True,
                'has_ship_identifier': 'mmsi' in df.columns,
                'has_dest': 'dest' in df.columns,
                'has_vessel_type': 'vessel_type' in df.columns,
                'has_flag_ctry': 'flag_ctry' in df.columns,
                'has_timestamp': 'postime' in df.columns
            },
            'coordinate_columns': {'lon': 'lon', 'lat': 'lat'},
            'ship_id_column': 'mmsi' if 'mmsi' in df.columns else None,
            'timestamp_column': 'postime' if 'postime' in df.columns else None,
            'total_ships': len(ship_groups) if 'mmsi' in df.columns else 0
        }
        
        return jsonify({
            'filename': filename,
            'data': data,
            'stats': stats,
            'ship_groups': ship_groups if 'mmsi' in df.columns else {},
            'global_time_range': global_time_range,
            'message': '数据读取成功',
            'has_multiple_ships': len(ship_groups) > 1 if 'mmsi' in df.columns else False
        })
        
    except Exception as e:
            app.logger.error(f"读取CSV错误: {str(e)}")
            app.logger.debug(traceback.format_exc())
            # 不向用户暴露详细错误信息
            return jsonify({'error': '读取CSV文件失败'}), 500



@app.route('/api/data/<filename>/ship/<ship_id>', methods=['GET'])
def get_ship_data(filename, ship_id):
    """获取指定文件中特定船只的数据"""
    try:
        # 安全检查，防止路径遍历攻击
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': '文件名不合法'}), 400
            
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        
        # 读取CSV文件
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(filepath, encoding='gbk')
            except Exception:
                return jsonify({'error': '文件编码错误，无法解析'}), 400
        
        # 数据预处理，只获取指定的字段：mmsi, lon, lat, dest, vessel_type
        df.columns = df.columns.str.lower()
        
        # 识别并标准化字段（与get_csv_data相同的逻辑）
        mmsi_columns = ['mmsi', 'mmsi_number', 'ship_mmsi']
        mmsi_column = None
        for col in mmsi_columns:
            if col in df.columns:
                mmsi_column = col
                break
        
        if not mmsi_column:
            return jsonify({'error': '文件中没有找到MMSI字段'}), 404
        
        lon_columns = ['lon', 'longitude', 'long', 'lng']
        lon_column = None
        for col in lon_columns:
            if col in df.columns:
                lon_column = col
                break
        
        lat_columns = ['lat', 'latitude', 'latitude_']
        lat_column = None
        for col in lat_columns:
            if col in df.columns:
                lat_column = col
                break
        
        dest_columns = ['dest', 'destination', 'port', 'dest_port']
        dest_column = None
        for col in dest_columns:
            if col in df.columns:
                dest_column = col
                break
        
        vessel_type_columns = ['vessel_type', 'vesseltype', 'vessel-type', 'type', 'ship_type']
        vessel_type_column = None
        for col in vessel_type_columns:
            if col in df.columns:
                vessel_type_column = col
                break
        
        # 构建新的DataFrame，只包含需要的字段
        new_df_data = {}
        
        if pd.api.types.is_numeric_dtype(df[mmsi_column]):
            new_df_data['mmsi'] = df[mmsi_column].astype(str)
        else:
            new_df_data['mmsi'] = df[mmsi_column].astype(str)
        
        if lon_column:
            new_df_data['lon'] = pd.to_numeric(df[lon_column], errors='coerce')
        else:
            return jsonify({'error': 'CSV文件中未找到经度字段(lon/longitude)'}), 400
        
        if lat_column:
            new_df_data['lat'] = pd.to_numeric(df[lat_column], errors='coerce')
        else:
            return jsonify({'error': 'CSV文件中未找到纬度字段(lat/latitude)'}), 400
        
        if dest_column:
            new_df_data['dest'] = df[dest_column].astype(str)
            new_df_data['dest'] = new_df_data['dest'].replace(['nan', 'None', 'null', 'NaN', 'NAN'], '')
            new_df_data['dest'] = new_df_data['dest'].fillna('')
        else:
            new_df_data['dest'] = ''
        
        if vessel_type_column:
            new_df_data['vessel_type'] = df[vessel_type_column].astype(str)
            new_df_data['vessel_type'] = new_df_data['vessel_type'].replace(['nan', 'None', 'null', 'NaN', 'NAN'], '')
            new_df_data['vessel_type'] = new_df_data['vessel_type'].fillna('')
        else:
            new_df_data['vessel_type'] = ''
        
        df = pd.DataFrame(new_df_data)
        
        # 筛选指定MMSI的数据
        ship_data = df[df['mmsi'] == ship_id]
        
        if len(ship_data) == 0:
            return jsonify({'error': '未找到指定MMSI的船只数据'}), 404
        
        # 过滤无效的经纬度数据
        ship_data = ship_data[(pd.notna(ship_data['lon'])) & (pd.notna(ship_data['lat']))]
        ship_data = ship_data[(ship_data['lon'] >= -180) & (ship_data['lon'] <= 180)]
        ship_data = ship_data[(ship_data['lat'] >= -90) & (ship_data['lat'] <= 90)]
        
        # 按时间排序
        if 'postime' in ship_data.columns and pd.api.types.is_datetime64_any_dtype(ship_data['postime']):
            ship_data_sorted = ship_data.sort_values('postime')
            app.logger.info(f"船只 {ship_id} 已按时间排序")
        else:
            ship_data_sorted = ship_data
        
        # 限制返回数据量
        max_rows = 50000  # 提高单船数据限制到5万轨迹点
        ship_data_limit = ship_data_sorted.head(max_rows)
        
        # 返回数据
        return jsonify({
            'filename': filename,
            'ship_id': ship_id,
            'mmsi': ship_id,
            'point_count': len(ship_data),
            'returned_points': len(ship_data_limit),
            'data': ship_data_limit.to_dict('records'),
            'bounds': {
                'min_lon': ship_data['lon'].min(),
                'max_lon': ship_data['lon'].max(),
                'min_lat': ship_data['lat'].min(),
                'max_lat': ship_data['lat'].max()
            },
            'has_timestamp': 'postime' in ship_data.columns,
            'is_sorted_by_time': 'postime' in ship_data.columns and pd.api.types.is_datetime64_any_dtype(ship_data['postime']),
            'message': '船只数据获取成功'
        })
        
    except Exception as e:
        app.logger.error(f"获取船只数据错误: {str(e)}")
        app.logger.debug(traceback.format_exc())
        return jsonify({'error': '获取船只数据失败'}), 500



@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    logging.info("接收到健康检查请求")
    return jsonify({
        "status": "healthy",
        "message": "船舶可视化后端服务运行正常",
        "version": "1.0.0",
        "features": [
            "文件上传",
            "CSV数据处理",
            "船舶轨迹生成",
            "直接文件读取功能已启用"
        ],
        "debug_mode": True,
        "timestamp": pd.Timestamp.now().isoformat()
    })

@app.route('/api/health-check', methods=['GET'])
def health_check_alias():
    """健康检查接口别名"""
    return health_check()

@app.route('/api/test', methods=['GET'])
def test_endpoint():
    """简单测试端点，用于验证服务是否正常响应"""
    logging.info("接收到测试请求")
    return jsonify({
        "status": "success",
        "message": "测试端点正常响应",
        "data": {
            "current_time": pd.Timestamp.now().isoformat(),
            "working_directory": os.getcwd(),
            "python_version": "3.x",
            "pandas_version": pd.__version__
        }
    })

@app.route('/', methods=['GET'])
def root():
    """根路径，用于测试服务是否运行"""
    return jsonify({
        "status": "running",
        "message": "船舶可视化后端服务正在运行",
        "version": "1.0.0",
        "endpoints": {
            "health": "/api/health",
            "upload": "/api/upload",
            "files": "/api/files",
            "data": "/api/data/<filename>",
            "test": "/api/test"
        },
        "timestamp": pd.Timestamp.now().isoformat()
    })

if __name__ == '__main__':
    # 从环境变量获取端口，默认为5000
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    # 启用调试模式以便更好地捕获和显示错误
    DEBUG = True
    app.config['DEBUG'] = DEBUG
    
    print("启动船舶可视化后端服务...")
    print(f"服务地址: http://{host}:{port}")
    print(f"上传文件目录: {app.config['UPLOAD_FOLDER']}")
    print(f"调试模式: {DEBUG}")
    print("=== 后端服务已启动，正在监听请求 ===")
    
    # 生产环境不应该开启debug模式
    app.run(host=host, port=port, debug=DEBUG)