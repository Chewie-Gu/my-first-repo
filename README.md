# AI 学习助手（追问式）

不只直接给答案，而是先反问、等你作答、诊断你的错因，再给结论和出处。

## 仓库结构

```text
src/
  retrieval/      # A：检索与追问（FTS5、BM25、追问阶梯）
               fts5_demo.py   ← 现在就能跑的检索 demo
  backend/        # B：后端与数据（SQLite 建表、接口、调用链）
  frontend/       # C：前端（问答页、轮次提示、引用跳页）
  eval/           # D：评测（题库、脚本、试用记录）
docs/             # 题库、对照表、失败案例（题库也可以放飞书，二选一）
data/index/       # 本地 SQLite，不进仓库
```

## 快速开始（每个人都要做一次）

```powershell
# 1. 克隆（把 <repo-url> 换成组里的仓库地址）
git clone <repo-url>
cd my-first-repo

# 2. 建虚拟环境并激活
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. 装依赖（用清华镜像）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 配 Key（第一次才需要）
Copy-Item .env.example .env

# 5. 验证检索通路
python src/retrieval/fts5_demo.py
```

第 5 步应打印 `FTS5 可用: True`，并对三个查询各返回 3 条带页码的结果。

## 协作约定

- 不直接推 `main`：每个人建自己的分支（如 `feat/retrieval-fts5`），推上去开 PR，由另一人 review 后再合并。
- `.env`、`*.db`、`.venv` 已在 `.gitignore` 里，不要提交。
- 提交信息统一前缀：`feat:` 新功能 / `fix:` 修 bug / `docs:` 文档 / `chore:` 杂项。
