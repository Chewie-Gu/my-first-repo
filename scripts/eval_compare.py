"""对比基线 search() 与改进版 search_improved() 在同一份课件、同一套题上的命中率。

运行：
    python scripts/eval_compare.py
"""

import csv
import re
import sys
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from retrieval.search import add_chunks, init_index, search, search_improved  # noqa: E402


def slide_text(slide) -> str:
    parts = []
    for shape in slide.shapes:
        if shape.has_text_frame and shape.text_frame.text.strip():
            parts.append(shape.text_frame.text.strip())
        if getattr(shape, "has_table", False):
            for row in shape.table.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))
    return "\n".join(parts)


def build_chunks():
    chunks = []
    for path in sorted((ROOT / "testPPT").glob("*.pptx")):
        for i, slide in enumerate(Presentation(str(path)).slides, 1):
            text = slide_text(slide)
            if len(text) >= 10:
                chunks.append((len(chunks) + 1, path.stem, i, text))
    return chunks


def ref_pages(ref: str) -> set[str]:
    """参考答案支持多页："第1章-25/26/27" → {第1章-25, 第1章-26, 第1章-27}。"""
    chapter, pages = ref.split("-", 1)
    return {f"{chapter}-{p}" for p in pages.split("/")}


def hit_stats(fn, conn, questions):
    top1 = top3 = 0
    missed = []
    for q in questions:
        refs = ref_pages(q[2])
        hits = fn(conn, q[1], 3)
        locs = [f"{h['course']}-{h['page']}" for h in hits]
        if locs and locs[0] in refs:
            top1 += 1
        if refs & set(locs):
            top3 += 1
        else:
            missed.append(q[0])
    return top1, top3, missed


def main() -> None:
    chunks = build_chunks()
    conn = init_index()
    add_chunks(conn, chunks)

    questions = list(csv.reader((ROOT / "docs" / "检索粗测-30题.csv").open(encoding="utf-8")))[1:]

    t1a, t3a, miss_a = hit_stats(search, conn, questions)
    t1b, t3b, miss_b = hit_stats(search_improved, conn, questions)

    print(f"文本块：{len(chunks)}   题目：{len(questions)}")
    print(f"{'':12}{'top1':>8}{'top3':>8}{'未召回':>10}")
    print(f"{'基线 FTS5':12}{t1a:>7}/30{t3a:>7}/30{len(miss_a):>9} 题")
    print(f"{'改进版':12}{t1b:>7}/30{t3b:>7}/30{len(miss_b):>9} 题")
    print(f"\n基线未召回：{','.join(miss_a) or '无'}")
    print(f"改进后未召回：{','.join(miss_b) or '无'}")

    print("\n逐题对比（序号 | 参考答案 | 基线top1 | 改进top1 | 改进top3是否含答案）")
    for q in questions:
        refs = ref_pages(q[2])
        a = search(conn, q[1], 3)
        b = search_improved(conn, q[1], 3)
        la = f"{a[0]['course']}-{a[0]['page']}" if a else "无"
        lb = f"{b[0]['course']}-{b[0]['page']}" if b else "无"
        in3 = "是" if refs & {f"{h['course']}-{h['page']}" for h in b} else "否"
        print(f"{q[0]:>2} | {q[2]:>14} | {la:>10} | {lb:>10} | {in3}")


if __name__ == "__main__":
    main()
