"""检索模块：中文分词 + FTS5 虚表 + bm25 排序。

给 B 的后端和 C 的前端调用，接口只有三个：
    conn = init_index()          # 建表（真实场景传 db 文件路径）
    add_chunks(conn, chunks)     # 灌入课件片段
    rows = search(conn, "数组越界会怎样", top_k=3)

返回的每一行是 dict：
    {"chunk_id": 3, "course": "第3章 数组", "page": 18,
     "text": "访问越界下标不会报错……", "score": -2.081}
score 是 bm25 分数，负数，越小越相关。
"""

import re
import sqlite3

import jieba

# 保留中文、字母、数字，其余符号当分隔符丢掉
KEEP = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]+")


def tokenize(text: str) -> str:
    """jieba 切词后用空格拼接 —— FTS5 只认空格分隔的 token，中文不切词几乎检不出。"""
    return " ".join(t for t in jieba.cut(text) if KEEP.fullmatch(t))


def init_index(db_path: str = ":memory:") -> sqlite3.Connection:
    """建 FTS5 虚表并返回连接。db_path 传文件路径就落盘，传 :memory: 就只在内存里。"""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id UNINDEXED,
            course,
            page     UNINDEXED,
            body,
            raw      UNINDEXED
        )
        """
    )
    return conn


def add_chunks(conn: sqlite3.Connection, chunks) -> None:
    """chunks 为 [(chunk_id, course, page, text), ...]，text 是原始中文，这里负责分词。"""
    conn.executemany(
        "INSERT INTO chunks_fts (chunk_id, course, page, body, raw) VALUES (?, ?, ?, ?, ?)",
        [(cid, course, page, tokenize(text), text) for cid, course, page, text in chunks],
    )
    conn.commit()


def search(conn: sqlite3.Connection, query: str, top_k: int = 3) -> list[dict]:
    """查询也走同一套分词，多个词之间用 OR，再靠 bm25 排序取前 top_k。"""
    terms = tokenize(query).split()
    if not terms:
        return []
    match_expr = " OR ".join(terms)
    sql = """
        SELECT chunk_id, course, page, raw, bm25(chunks_fts) AS score
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
        ORDER BY score
        LIMIT ?
    """
    rows = conn.execute(sql, (match_expr, top_k)).fetchall()
    return [
        {"chunk_id": cid, "course": course, "page": page, "text": raw, "score": score}
        for cid, course, page, raw, score in rows
    ]


# ── 改进版：停用词 + 覆盖度 + 长度归一化 ──────────────────────────
# 背景（W1 基线实测）：top1 只有 47%，且 5 道题 top3 都没召回。
# 原因有三条，这里各改一处：
#   1. 问句里的"为什么/怎么/会"在课件里到处都是，参与匹配会把无关页顶上来 → 停用词
#   2. 只看 bm25 词频，命中 1 个词的短页能压过命中 4 个词的长页 → 覆盖度优先
#   3. 长页词多、词频高，天然占便宜（第3章-55页出现在 7 道题里）→ 分数除以页长平方根

STOPWORDS = {
    "为什么", "什么", "怎么", "怎样", "如何", "哪些", "哪个", "多少", "几步", "哪几",
    "区别", "关系", "之间", "时候", "情况", "作用", "分别", "一下", "代表", "一般",
    "是", "的", "和", "与", "或", "会", "能", "要", "在", "有", "里", "中", "上下",
    "吗", "呢", "吧", "这", "那", "个", "就", "都", "还", "也", "把", "被", "从", "到",
    "哪", "了", "过", "着", "两个", "几", "步", "属于", "通常", "可以", "需要", "应该",
}

# 课件里用表格/代码表达、学生却用概念词提问 —— 这类"词汇不匹配"排序怎么调都救不回来，
# 只能给概念词挂上页面里真正出现的词。只在同义/近义范围内扩展，不做自由联想。
SYNONYMS = {
    "相除": ["除法", "除"],
    "除": ["除法", "相除"],
    "小数": ["float", "浮点", "浮点型"],
    "整数": ["int", "整型"],
    "转义字符": ["反斜杠", "转义"],
    "反斜杠": ["转义字符", "转义"],
    "流程": ["步骤", "编译", "连接", "运行", "调试"],
    "执行流程": ["编译", "连接", "运行", "调试"],
    "字符": ["字母", "ASCII"],
    "ascii": ["字符", "字母", "65"],
    "ascii码": ["字符", "字母", "65"],
}
SYN_WEIGHT = 0.5          # 扩展词的权重：命中它只算命中半个原词


def query_terms(query: str) -> list[str]:
    """切词后去掉停用词和单字母噪声（C、A、n、t 这类在代码页里满屏都是）。"""
    tokens = [t for t in jieba.cut(query) if KEEP.fullmatch(t)]
    return [t for t in tokens if t not in STOPWORDS and not (len(t) == 1 and t.isascii())]


def search_improved(conn: sqlite3.Connection, query: str, top_k: int = 3) -> list[dict]:
    """覆盖度为主、bm25/页长 为辅的排序。返回结构与 search() 完全一致，可直接替换。"""
    terms = query_terms(query)
    if not terms:
        return []

    # 原词权重 1，同义词权重 0.5；覆盖度按权重和计
    weighted: dict[str, float] = {t: 1.0 for t in terms}
    for t in terms:
        for syn in SYNONYMS.get(t, []):
            if syn not in weighted:
                weighted[syn] = SYN_WEIGHT
    total_weight = sum(weighted.values())
    match_terms = list(weighted)

    # 先多取候选（上限 80），再在内存里重排
    sql = """
        SELECT chunk_id, course, page, raw, body, bm25(chunks_fts) AS score
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
        ORDER BY score
        LIMIT 80
    """
    rows = conn.execute(sql, (" OR ".join(match_terms),)).fetchall()

    ranked = []
    for chunk_id, course, page, raw, body, bm25_score in rows:
        body_terms = set(body.split())
        coverage = sum(w for t, w in weighted.items() if t in body_terms) / total_weight
        length_penalty = max(len(body_terms), 1) ** 0.5
        bonus = -bm25_score / length_penalty    # bm25 是负数，取反后越大越相关
        ranked.append((coverage + 0.1 * bonus, chunk_id, course, page, raw, bm25_score))

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [
        {"chunk_id": cid, "course": course, "page": page, "text": raw, "score": bm}
        for _, cid, course, page, raw, bm in ranked[:top_k]
    ]


# 自测用样本，真实场景由 B 的解析结果替代
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


if __name__ == "__main__":
    opts = [r[0] for r in sqlite3.connect(":memory:").execute("pragma compile_options")]
    print("FTS5 可用:", any("ENABLE_FTS5" in o for o in opts))

    conn = init_index()
    add_chunks(conn, SAMPLE_CHUNKS)
    for q in ["数组越界会怎样", "指针和数组的关系", "函数里改了参数为什么不生效"]:
        print(f"\n查询：{q}")
        for hit in search(conn, q):
            print(f"  #{hit['chunk_id']} {hit['course']} 第{hit['page']}页 "
                  f"bm25={hit['score']:.3f}  {hit['text'][:20]}")
