"""程序入口（最小版）。

现在只做三件事：读配置、自检环境、打印调用链占位。
解析、检索、追问的具体实现分别由 B / A / C 填进各自模块，这里只负责串起来。

运行：
    python src/main.py
"""

import os
import sqlite3

from dotenv import load_dotenv

# 调用链占位：按顺序由不同人实现，先冻结顺序，避免各自改接口
CALL_CHAIN = [
    ("1. 解析课件", "backend/parser.py", "B"),
    ("2. 建索引", "backend/index.py", "B"),
    ("3. 检索片段", "retrieval/search.py", "A"),
    ("4. 生成追问", "retrieval/followup.py", "A"),
    ("5. 诊断作答", "retrieval/diagnose.py", "A"),
    ("6. 汇总结论", "backend/answer.py", "B"),
    ("7. 记录轮次", "backend/turn_log.py", "B"),
]


def check_env() -> bool:
    load_dotenv()
    db_path = os.getenv("DB_PATH", "data/index/course.db")
    has_key = bool(os.getenv("LLM_API_KEY")) and os.getenv("LLM_API_KEY") != "在这里填你自己的Key"

    conn = sqlite3.connect(":memory:")
    fts5 = any("ENABLE_FTS5" in row[0] for row in conn.execute("pragma compile_options"))
    conn.close()

    print(f"FTS5 可用      : {fts5}")
    print(f"数据库路径      : {db_path}")
    print(f"LLM Key 已配置  : {has_key}")
    return fts5


def main() -> None:
    print("AI 学习助手（追问式）· 最小入口\n")
    check_env()

    print("\n调用链（当前只有占位，没有实现）：")
    for step, module, owner in CALL_CHAIN:
        print(f"  {step:<12} {module:<24} 负责人 {owner}")

    print("\n下一步：跑 python src/retrieval/fts5_demo.py 验证检索通路。")


if __name__ == "__main__":
    main()
