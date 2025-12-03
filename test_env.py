# 简单的环境测试脚本
import sys
import os

print("=== 环境测试开始 ===")
print(f"Python版本: {sys.version}")
print(f"当前工作目录: {os.getcwd()}")
print(f"Python路径: {sys.executable}")
print(f"环境变量PATH: {os.environ.get('PATH', '未设置')}")
print(f"目录内容: {os.listdir('.')}")

# 尝试导入常用模块
try:
    import flask
    print(f"Flask版本: {flask.__version__}")
except ImportError:
    print("警告: 无法导入Flask模块")

try:
    import pandas
    print(f"Pandas版本: {pandas.__version__}")
except ImportError:
    print("警告: 无法导入Pandas模块")

print("=== 环境测试结束 ===")