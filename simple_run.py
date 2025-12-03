#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单启动脚本
"""

from app import app

if __name__ == '__main__':
    # 关闭调试模式和自动重载以提高稳定性
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)