"""把 testPPT 下的课件抽成文本块 → 建 FTS5 索引 → 跑 30 题 → 输出标注辅助表。

运行：
    python scripts/eval_retrieval.py

产出：
    docs/检索粗测-结果.csv   每题 top3 候选页，人工核对后填「正确答案」两列
"""

import csv
import sys
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from retrieval.search import add_chunks, init_index, search  # noqa: E402

PPT_DIR = ROOT / "testPPT"
QUES_CSV = ROOT / "docs" / "检索粗测-30题.csv"
OUT_CSV = ROOT / "docs" / "检索粗测-结果.csv"


def slide_text(slide) -> str:
    """抽一页的所有文字：标题、正文、表格、备注。"""
    parts = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            text = shape.text_frame.text.strip()
            if text:
                parts.append(text)
        if getattr(shape, "has_table", False):
            for row in shape.table.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))
    if slide.has_notes_slide:
        frame = slide.notes_slide.notes_text_frame
        note = frame.text.strip() if frame is not None else ""
        if note:
            parts.append("备注：" + note)
    return "\n".join(parts)


def build_chunks():
    """按「一章一个 PPT、一页一个块」抽取，返回 (chunks, 统计)。"""
    chunks, skipped = [], []
    for path in sorted(PPT_DIR.glob("*.pptx")):
        prs = Presentation(str(path))
        for i, slide in enumerate(prs.slides, start=1):
            text = slide_text(slide)
            if len(text) < 10:            # 封面、纯图片页、目录页，没正文
                skipped.append(f"{path.stem}-{i}")
                continue
            chunks.append((len(chunks) + 1, path.stem, i, text))
    return chunks, skipped


def main() -> None:
    if not PPT_DIR.exists():
        print(f"找不到课件目录：{PPT_DIR}")
        return

    chunks, skipped = build_chunks()
    print(f"抽取完成：{len(chunks)} 个文本块，跳过 {len(skipped)} 页（无正文/纯图片）")
    print(f"跳过页：{', '.join(skipped) if skipped else '无'}")

    conn = init_index()
    add_chunks(conn, chunks)

    with QUES_CSV.open(encoding="utf-8") as f:
        questions = [row for row in csv.reader(f)][1:]

    rows, empty = [], 0
    for q in questions:
        hits = search(conn, q[1], top_k=3)
        if not hits:
            empty += 1
        cand = [f"{h['course']}-第{h['page']}页：{h['text'][:28].replace(chr(10), ' ')}"
                for h in hits]
        cand += [""] * (3 - len(cand))
        rows.append([q[0], q[1], *cand])

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["序号", "问题", "候选1（top1）", "候选2", "候选3",
                         "正确答案（章-页）", "top1是否正确", "正确答案排第几"])
        for row in rows:
            writer.writerow(row + ["", "", ""])

    print(f"30 题跑完：{len(rows)} 题，完全无召回 {empty} 题")
    print(f"结果已写入：{OUT_CSV}")


if __name__ == "__main__":
    main()
