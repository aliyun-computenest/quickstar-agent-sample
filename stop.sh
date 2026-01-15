#!/bin/bash

# Quickstar Agent 停止服务脚本
# 适用于 Linux ECS

set -e

echo "========================================="
echo "Quickstar Agent 停止服务脚本"
echo "========================================="

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 root 用户运行此脚本"
    exit 1
fi

# 停止前端服务
echo "正在停止前端服务..."
if systemctl is-active --quiet frontend.service; then
    systemctl stop frontend.service
    echo "✓ 前端服务已停止"
else
    echo "✓ 前端服务未运行"
fi

# 停止后端服务
echo "正在停止后端服务..."
if systemctl is-active --quiet backend.service; then
    systemctl stop backend.service
    echo "✓ 后端服务已停止"
else
    echo "✓ 后端服务未运行"
fi

# 禁用服务自启动
echo "正在禁用服务自启动..."
systemctl disable frontend.service 2>/dev/null || true
systemctl disable backend.service 2>/dev/null || true
echo "✓ 服务自启动已禁用"

echo ""
echo "========================================="
echo "所有服务已停止"
echo "========================================="
echo ""
echo "如需重新启动服务，请运行: ./deploy.sh"
echo "或单独启动: systemctl start backend.service && systemctl start frontend.service"
echo ""
