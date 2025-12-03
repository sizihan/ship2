#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
超简化的测试服务器
用于诊断环境问题
"""

from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Minimal Flask Server Running"})

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    print("Starting minimal server on http://0.0.0.0:5002")
    app.run(host='0.0.0.0', port=5002, debug=False, use_reloader=False)