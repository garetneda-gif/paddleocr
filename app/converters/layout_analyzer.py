"""基于 bbox 坐标的版面分析 — 行合并、段落分组、标题推断、分栏检测。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.document_result import BlockResult, PageResult
from app.models.enums import BlockType


@dataclass
class TextLine:
    """合并后的文本行（同一行内多个 block 合并）。"""
    blocks: list[BlockResult]
    y_top: float = 0
    y_bottom: float = 0
    x_left: float = 0
    x_right: float = 0
    text: str = ""

    def __post_init__(self):
        if self.blocks:
            self.y_top = min(b.bbox[1] for b in self.blocks)
            self.y_bottom = max(b.bbox[3] for b in self.blocks)
            self.x_left = min(b.bbox[0] for b in self.blocks)
            self.x_right = max(b.bbox[2] for b in self.blocks)
            self.text = " ".join(b.text for b in self.blocks if b.text)

    @property
    def height(self) -> float:
        return self.y_bottom - self.y_top

    @property
    def center_y(self) -> float:
        return (self.y_top + self.y_bottom) / 2


@dataclass
class Paragraph:
    """段落：多行聚合，附带推断的 block_type。"""
    lines: list[TextLine]
    block_type: BlockType = BlockType.PARAGRAPH
    column: int = 0  # 0=全宽, 1=左栏, 2=右栏

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        x1 = min(l.x_left for l in self.lines)
        y1 = min(l.y_top for l in self.lines)
        x2 = max(l.x_right for l in self.lines)
        y2 = max(l.y_bottom for l in self.lines)
        return (x1, y1, x2, y2)

    @property
    def avg_line_height(self) -> float:
        heights = [l.height for l in self.lines]
        return sum(heights) / len(heights) if heights else 0


def analyze_page(page: PageResult) -> list[Paragraph]:
    """对单页做版面分析，返回按阅读顺序排列的段落列表。"""
    if not page.blocks:
        return []

    lines = _merge_blocks_to_lines(page.blocks)
    columns = _detect_columns(lines, page.width)

    if columns == 1:
        paragraphs = _group_lines_to_paragraphs(lines, page)
    else:
        left, right = _split_columns(lines, page.width)
        left_paras = _group_lines_to_paragraphs(left, page, column=1)
        right_paras = _group_lines_to_paragraphs(right, page, column=2)
        paragraphs = _interleave_columns(left_paras, right_paras)

    _infer_block_types(paragraphs, page)
    return paragraphs


def _merge_blocks_to_lines(blocks: list[BlockResult]) -> list[TextLine]:
    """把 y 坐标重叠的 block 合并为同一行。"""
    if not blocks:
        return []

    sorted_blocks = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
    lines: list[TextLine] = []
    current_blocks = [sorted_blocks[0]]

    for block in sorted_blocks[1:]:
        last = current_blocks[-1]
        last_cy = (last.bbox[1] + last.bbox[3]) / 2
        last_h = last.bbox[3] - last.bbox[1]
        cur_cy = (block.bbox[1] + block.bbox[3]) / 2

        # y 中心距离 < 行高的 50% → 同一行
        if last_h > 0 and abs(cur_cy - last_cy) < last_h * 0.5:
            current_blocks.append(block)
        else:
            current_blocks.sort(key=lambda b: b.bbox[0])
            lines.append(TextLine(blocks=list(current_blocks)))
            current_blocks = [block]

    if current_blocks:
        current_blocks.sort(key=lambda b: b.bbox[0])
        lines.append(TextLine(blocks=list(current_blocks)))

    return lines


def _detect_columns(lines: list[TextLine], page_width: int) -> int:
    """检测页面是单栏还是双栏布局。"""
    if len(lines) < 4 or page_width <= 0:
        return 1

    mid_x = page_width / 2
    gap_zone_left = mid_x * 0.4
    gap_zone_right = mid_x * 1.6

    left_only = 0
    right_only = 0
    crossing = 0

    for line in lines:
        in_left = line.x_right < gap_zone_right and line.x_left < mid_x
        in_right = line.x_left > gap_zone_left and line.x_right > mid_x
        spans_both = line.x_left < gap_zone_left and line.x_right > gap_zone_right

        if spans_both:
            crossing += 1
        elif line.x_right < mid_x * 0.95:
            left_only += 1
        elif line.x_left > mid_x * 1.05:
            right_only += 1
        else:
            crossing += 1

    total = left_only + right_only + crossing
    if total == 0:
        return 1

    # 超过 40% 的行只在一侧 → 双栏
    if (left_only + right_only) / total > 0.4 and left_only > 2 and right_only > 2:
        return 2

    return 1


def _split_columns(lines: list[TextLine], page_width: int) -> tuple[list[TextLine], list[TextLine]]:
    """将行按左右栏拆分。"""
    mid_x = page_width / 2
    left = []
    right = []
    for line in lines:
        center_x = (line.x_left + line.x_right) / 2
        if center_x < mid_x:
            left.append(line)
        else:
            right.append(line)
    return left, right


def _group_lines_to_paragraphs(
    lines: list[TextLine], page: PageResult, column: int = 0,
) -> list[Paragraph]:
    """根据行间距将行分组为段落。"""
    if not lines:
        return []

    lines.sort(key=lambda l: l.y_top)
    avg_h = sum(l.height for l in lines) / len(lines) if lines else 20

    paragraphs: list[Paragraph] = []
    current_lines = [lines[0]]

    for line in lines[1:]:
        prev = current_lines[-1]
        gap = line.y_top - prev.y_bottom

        # 行间距 > 平均行高的 0.8 倍 → 新段落
        if gap > avg_h * 0.8:
            paragraphs.append(Paragraph(lines=list(current_lines), column=column))
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        paragraphs.append(Paragraph(lines=list(current_lines), column=column))

    return paragraphs


def _interleave_columns(left: list[Paragraph], right: list[Paragraph]) -> list[Paragraph]:
    """按 y 坐标交错合并左右栏段落（阅读顺序）。"""
    all_paras = left + right
    all_paras.sort(key=lambda p: p.bbox[1])
    return all_paras


def _infer_block_types(paragraphs: list[Paragraph], page: PageResult) -> None:
    """根据字体大小（行高）和位置推断段落类型。"""
    if not paragraphs:
        return

    avg_heights = [p.avg_line_height for p in paragraphs if p.avg_line_height > 0]
    if not avg_heights:
        return
    median_h = sorted(avg_heights)[len(avg_heights) // 2]

    for para in paragraphs:
        if para.avg_line_height <= 0:
            continue

        # 行高 > 中位数 1.4 倍 且 行数少 → 标题
        if para.avg_line_height > median_h * 1.4 and len(para.lines) <= 3:
            para.block_type = BlockType.TITLE
        # 单行且文字短、居中 → 标题/图注
        elif (len(para.lines) == 1
              and len(para.text) < 60
              and page.width > 0):
            line = para.lines[0]
            center_offset = abs((line.x_left + line.x_right) / 2 - page.width / 2)
            if center_offset < page.width * 0.15:
                if para.avg_line_height > median_h * 1.2:
                    para.block_type = BlockType.TITLE
