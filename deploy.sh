#!/bin/bash

# Quickstar Agent 一键部署脚本
# 适用于 Linux ECS

set -e

echo "========================================="
echo "Quickstar Agent 一键部署脚本"
echo "========================================="

# 配置变量
PROJECT_DIR="/root/code_deploy_application"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
PYTHON_VERSION="python3"

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 root 用户运行此脚本"
    exit 1
fi

# 1. 安装系统依赖
echo "步骤 1/8: 安装系统依赖..."
yum update -y
sudo dnf remove -y podman podman-docker buildah skopeo runc
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
yum install -y nodejs npm nginx docker-ce docker-ce-cli containerd.io -y

# 2. 启动 Docker 服务
echo "步骤 2/8: 启动 Docker 服务..."
systemctl start docker
systemctl enable docker

# 验证 Docker 是否正常运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker 启动失败，请检查 Docker 安装"
    exit 1
fi
echo "Docker 已成功启动"

# 3. 创建项目目录
echo "步骤 3/8: 创建项目目录..."
mkdir -p $PROJECT_DIR

# 4. 部署后端
echo "步骤 4/8: 部署后端服务..."
cd $BACKEND_DIR

pip3 install -r requirements.txt --timeout 1000

# 5. 部署前端
echo "步骤 5/8: 部署前端服务..."
cd $FRONTEND_DIR

# 安装依赖
npm install

# 6. 安装 systemd 服务
echo "步骤 6/8: 安装 systemd 服务..."
cd $PROJECT_DIR
cp backend.service /etc/systemd/system/
cp frontend.service /etc/systemd/system/

# 重新加载 systemd
systemctl daemon-reload

# 7. 启动服务
echo "步骤 7/8: 启动服务..."
systemctl enable backend.service
systemctl start backend.service

sleep 3

systemctl enable frontend.service
systemctl start frontend.service

# 8. 验证服务状态
echo "步骤 8/8: 验证服务状态..."
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
echo "  1. 请确保已配置 $BACKEND_DIR/.env 文件中的必要环境变量"
echo "  2. 如需修改服务端口，请编辑对应的 .service 文件"
echo "  3. 前端默认运行在开发模式，生产环境建议使用 nginx 部署"
echo "  4. 项目代码应位于 /root/quickstar-agent-sample 目录下"
echo "  5. Docker 已安装并启动，可用于容器化部署"
echo ""
echo "Docker 相关命令:"
echo "  - 查看 Docker 状态: systemctl status docker"
echo "  - 查看 Docker 版本: docker --version"
echo "  - 查看运行中的容器: docker ps"
echo "  - 停止 Docker: systemctl stop docker"
echo ""
