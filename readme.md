# windows 指令

## 創建 虛擬環境

python -m venv myenv

## 進入 虛擬環境

myenv\Scripts\activate

## 退出 虛擬環境

deactivate

## 刪除 虛擬環境

rd /s /q myenv

## 匯出當前安裝的套件

pip freeze > requirements.txt

## 從 requirements.txt 安裝套件

pip install -r requirements.txt

## 啟動 FastAPI 應用

uvicorn main:app --reload

# git

## 在本地初始化 Git 倉庫

1. cd /path/to/your/dotnet-project
2. git init

## 配置 .gitignore 文件

新增 .gitignore

## 將文件加入本地倉庫

git add .
git commit -m "Initial commit for fastapi  project"

## 關聯到遠端 github

git remote add origin https://github.com/lauchiwai/py_chat_service.git


# docker command

## 清理构建缓存

docker-compose down -v --remove-orphans
docker builder prune -af

## 重新构建

docker-compose up --build -d

## 查看依赖安装情况

docker exec -it py_chat_service-chat-service-1 pip list
