# PPG Blood Pressure Prediction

基于 PPG 波形的血压预测系统。项目包含前端、后端、MySQL、Redis、Milvus 向量库和模拟 PPG 数据，主要用于演示一条完整的预测业务链路。

## 项目简介

核心流程：

```text
上传 PPG CSV
-> 信号预处理
-> 提取 24 维特征
-> PCA 变换
-> 整理成 128 维向量
-> Milvus 检索相似样本
-> 根据相似样本血压加权平均
-> 保存预测记录
```

## 技术栈

后端：

- FastAPI
- SQLAlchemy
- MySQL
- Redis
- Milvus
- LangGraph
- NumPy / Pandas / SciPy / scikit-learn

前端：

- Vue 3
- Vite
- Element Plus
- ECharts

部署：

- Docker
- Docker Compose
- Nginx

## 目录结构

```text
backend/       FastAPI 后端
frontend/      Vue 前端
deploy/        Docker Compose、Nginx、初始化脚本和部署说明
mock-data/     模拟 PPG CSV 和初始化数据
```

后端重点目录：

```text
backend/app/routers/    API 接口层
backend/app/services/   业务逻辑层
backend/app/models/     数据库表和接口模型
backend/app/utils/      鉴权、JWT、响应格式、异常
```

## 一键启动

确保本机已安装 Docker 和 Docker Compose。

在项目根目录执行：

```powershell
docker compose -f deploy/docker-compose.local.yml up -d --build
```

访问：

```text
前端：http://127.0.0.1
后端健康检查：http://127.0.0.1:8000/api/v1/health
```

如果本机 80 端口被占用：

```powershell
$env:FRONTEND_HOST_PORT="8080"
docker compose -f deploy/docker-compose.local.yml up -d --build
```

然后访问：

```text
http://127.0.0.1:8080
```

## 初始化 Milvus 特征库

第一次启动后，需要初始化 Milvus 特征库，否则预测时找不到相似样本。

可以通过管理员接口：

```text
POST /api/v1/admin/milvus/initialize
```

该接口需要管理员 token。

也可以参考：

```text
deploy/README-milvus.md
backend/scripts/ensure_admin.py
```

## 常用命令

查看容器：

```powershell
docker ps
```

查看后端日志：

```powershell
docker logs -f ppg-backend
```

查看前端日志：

```powershell
docker logs -f ppg-frontend
```

停止项目：

```powershell
docker compose -f deploy/docker-compose.local.yml down
```

## 本地开发

后端：

```powershell
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

## 环境变量

后端示例配置：

```text
backend/.env.example
backend/.env.production.example
```

注意不要提交真实 `.env` 文件。

## 数据存储

```text
MySQL：用户、预测记录、PPG 原始波形、系统配置
Milvus：PPG 特征向量和相似检索数据
Redis：配置缓存、用户缓存、预测 checkpoint
本地文件：mock PPG CSV、PCA 模型文件
```

## 说明

项目中的 PCA 模型文件位于：

```text
backend/app/static/pca_model.pkl
```

如果修改了特征提取逻辑，需要重新训练 PCA，并重新初始化 Milvus 特征库，避免旧向量和新向量不在同一个特征空间里。
