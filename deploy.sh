#!/bin/bash

# Quickstar Agent 一键部署脚本
# 适用于 Linux ECS

set -e

echo "========================================="
echo "Quickstar Agent 一键部署脚本"
echo "========================================="

# 配置变量
PROJECT_DIR="/root/quickstar-agent-sample"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PYTHON_VERSION="python3"

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 root 用户运行此脚本"
    exit 1
fi

# 1. 安装系统依赖
echo "步骤 1/7: 安装系统依赖..."
apt-get update
apt-get install -y nodejs npm nginx

# 2. 创建项目目录
echo "步骤 2/7: 创建项目目录..."
mkdir -p $PROJECT_DIR

# 3. 部署后端
echo "步骤 3/7: 部署后端服务..."
cd $BACKEND_DIR

pip3 install -r requirements.txt

# 4. 部署前端
echo "步骤 4/7: 部署前端服务..."
cd $FRONTEND_DIR

# 安装依赖
npm install

# 5. 安装 systemd 服务
echo "步骤 5/7: 安装 systemd 服务..."
cp backend.service /etc/systemd/system/
cp frontend.service /etc/systemd/system/

# 重新加载 systemd
systemctl daemon-reload

# 6. 启动服务
echo "步骤 6/7: 启动服务..."
systemctl enable backend.service
systemctl start backend.service

sleep 3

systemctl enable frontend.service
systemctl start frontend.service

# 7. 验证服务状态
echo "步骤 7/7: 验证服务状态..."
echo ""
echo "后端服务状态:"
systemctl status backend.service --no-pager || true

echo ""
echo "前端服务状态:"
systemctl status frontend.service --no-pager || true

echo ""
echo "========================================="
echo "部署完成！"
echo "========================================="
echo ""
echo "服务访问地址:"
echo "  - 后端 API: http://localhost:9000"
echo "  - 前端界面: http://localhost:3000"
echo ""
echo "常用命令:"
echo "  - 查看后端日志: journalctl -u backend.service -f"
echo "  - 查看前端日志: journalctl -u frontend.service -f"
echo "  - 重启后端: systemctl restart backend.service"
echo "  - 重启前端: systemctl restart frontend.service"
echo ""
echo "注意事项:"
echo "  1. 请确保已配置 $BACKEND_DIR/.env 文件中的必要环境变量
  2. 如需修改服务端口，请编辑对应的 .service 文件
  3. 前端默认运行在开发模式，生产环境建议使用 nginx 部署
  4. 项目代码应位于 /root/quickstar-agent-sample 目录下"
echo ""
