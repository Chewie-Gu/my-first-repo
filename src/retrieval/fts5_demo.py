"""FTS5 中文检索最小跑通 demo（A 的 W1 起点）。

目标：不依赖 B 的后端、不依赖真实 PPT，先用 8 段自备文本验证
"中文分词 + FTS5 虚表 + bm25 排序" 这条通路能不能召回正确段落。

运行：
    python src/retrieval/fts5_demo.py

看三个东西：
1. 第一行是否打印 FTS5 可用（ENABLE_FTS5 在编译选项里）；
2. 输入"数组 越界"能否召回"数组下标"那段；
3. 打印出的 bm25 分数是否为负数且越小越相关。
"""

import re
import sqlite3

import jieba

# 自备样本：C 语言课件的 8 个段落（真实场景换成 B 解析出来的 chunk）
SAMPLE_CHUNKS = [
    (1, "第3章 数组", 12, "数组是一组相同类型元素的集合，元素在内存中连续存放。"),
    (2, "第3章 数组", 14, "数组下标从 0 开始，最后一个元素的下标是长度减 1。"),
    (3, "第3章 数组", 18, "访问越界下标不会报错，但会读到其他变量的内存，属于未定义行为。"),
    (4, "第4章 指针", 6, "指针变量存放的是另一个变量的地址，通过 * 运算符可以取到该地址上的值。"),
    (5, "第4章 指针", 9, "数组名在多数表达式中会退化为指向首元素的指针。"),
    (6, "第5章 函数", 4, "函数调用时实参按值传递给形参，形参的修改不会影响实参。"),
    (7, "第5章 函数", 11, "若要在函数内修改外部变量，需要传入该变量的地址。"),
    (8, "第6章 结构体", 3, "结构体把多个不同类型的数据打包成一个整体，用 . 访问成员。"),
]

# 保留中文、字母、数字，其余符号当分隔符丢掉
KEEP = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]+")


def cut(text: str) -> str:
    """jieba 切词后用空格拼接 —— FTS5 只认空格分隔的 token。"""
    tokens = [t for t in jieba.cut(text) if KEEP.fullmatch(t)]
    return " ".join(tokens)


def build_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            chunk_id UNINDEXED,
            course,
            page  UNINDEXED,
            body
        )
        """
    )
    conn.executemany(
        "INSERT INTO chunks_fts (chunk_id, course, page, body) VALUES (?, ?, ?, ?)",
        [(cid, course, page, cut(text)) for cid, course, page, text in SAMPLE_CHUNKS],
    )
    return conn


def search(conn: sqlite3.Connection, query: str, top_k: int = 3):
    # 查询也走同一套分词，多个词之间用 OR，再靠 bm25 排序
    q = " OR ".join(cut(query).split())
    sql = """
        SELECT chunk_id, course, page, body, bm25(chunks_fts) AS score
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    return conn.execute(sql, (q, top_k)).fetchall()


def main() -> None:
    opts = [row[0] for row in sqlite3.connect(":memory:").execute("pragma compile_options")]
    print("FTS5 可用:", any("ENABLE_FTS5" in o for o in opts))

    conn = build_db()
    for query in ["数组越界会怎样", "指针和数组的关系", "函数里改了参数为什么不生效"]:
        print(f"\n查询：{query}")
        rows = search(conn, query)
        if not rows:
            print("  （无召回，检查分词或用 OR 放宽）")
        for cid, course, page, body, score in rows:
            print(f"  #{cid} {course} 第{page}页  bm25={score:.3f}")


if __name__ == "__main__":
    main()
