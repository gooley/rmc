"""Convert blocks to svg file.

Code originally from https://github.com/lschwetlick/maxio through
https://github.com/chemag/maxio .
"""

from io import TextIOWrapper
import logging
import math
import string

from typing import Iterable

from dataclasses import dataclass

from rmscene import (
    read_blocks,
    Block,
    RootTextBlock,
    AuthorIdsBlock,
    MigrationInfoBlock,
    PageInfoBlock,
    SceneTreeBlock,
    TreeNodeBlock,
    SceneGroupItemBlock,
    SceneLineItemBlock,
)
from rmscene.text import TextDocument

from .writing_tools import (
    Pen,
)

_logger = logging.getLogger(__name__)


SCREEN_WIDTH = 1404
SCREEN_HEIGHT = 1872

SVG_HEADER = string.Template("""
<svg xmlns="http://www.w3.org/2000/svg" height="$height" width="$width">
    <script type="application/ecmascript"> <![CDATA[
        var visiblePage = 'p1';
        function goToPage(page) {
            document.getElementById(visiblePage).setAttribute('style', 'display: none');
            document.getElementById(page).setAttribute('style', 'display: inline');
            visiblePage = page;
        }
    ]]>
    </script>
    <defs>
        <filter x="-10%" y="-10%" width="120%" height="120%" filterUnits="objectBoundingBox" id="mechPencilTexture">
            <feTurbulence type="fractalNoise" baseFrequency="0.5" numOctaves="5" stitchTiles="stitch" result="f1">
            </feTurbulence>
            <feColorMatrix type="matrix" values="0 0 0 0 0, 0 0 0 0 0, 0 0 0 0 0, 0 0 0 -1.5 1.5" result="f2">
            </feColorMatrix>
            <feComposite operator="in" in2="f2b" in="SourceGraphic" result="f3">
            </feComposite>
            <feTurbulence type="fractalNoise" baseFrequency="1.2" numOctaves="3" result="noise">
            </feTurbulence>
            <feDisplacementMap xChannelSelector="R" yChannelSelector="G" scale="2.5" in="f3" result="f4">
            </feDisplacementMap>
        </filter>
        <filter x="-2000%" y="-2000%" width="5000%" height="5000%" filterUnits="objectBoundingBox" id="pencilTexture">
            <feTurbulence type="fractalNoise" baseFrequency="0.5" numOctaves="10" stitchTiles="stitch" result="f1">
            </feTurbulence>
            <feColorMatrix type="matrix" values="0 0 0 0 0, 0 0 0 0 0, 0 0 0 0 0, 0 0 0 -1.9 1.7" result="f2">
            </feColorMatrix>
            <feComposite operator="in" in2="f2" in="SourceGraphic" result="f3">
            </feComposite>
            <feTurbulence type="fractalNoise" baseFrequency="1.2" numOctaves="3" result="noise">
            </feTurbulence>
            <feDisplacementMap xChannelSelector="R" yChannelSelector="G" scale="2" in="f3" result="f4">
            </feDisplacementMap>
        </filter>
    </defs>
""")
XPOS_SHIFT = SCREEN_WIDTH / 2


@dataclass
class SvgDocInfo:
    height: int
    width: int
    xpos_delta: float
    ypos_delta: float


def rm_to_svg(rm_path, svg_path, debug=0):
    """Convert `rm_path` to SVG at `svg_path`."""
    with open(rm_path, "rb") as infile, open(svg_path, "wt") as outfile:
        blocks = read_blocks(infile)
        blocks_to_svg(blocks, outfile, debug)


def blocks_to_svg(blocks: Iterable[Block], output, debug=0):
    """Convert Blocks to SVG."""

    # we need to process the blocks twice to understand the dimensions, so
    # let's put the iterable into a list
    blocks = list(blocks)

    # get document dimensions
    svg_doc_info = get_dimensions(blocks, debug)

    # add svg header
    output.write(SVG_HEADER.substitute(height=svg_doc_info.height, width=svg_doc_info.width))
    output.write('\n')

    # add svg page info
    output.write('    <g id="p1" style="display:inline">\n')
    output.write('        <filter id="blurMe"><feGaussianBlur in="SourceGraphic" stdDeviation="10" /></filter>\n')

    for idx, block in enumerate(blocks):

        if isinstance(block, SceneLineItemBlock):
            output.write(f'        <!-- block idx: {idx} -->\n')
            draw_stroke(block, output, svg_doc_info, debug)
        elif isinstance(block, RootTextBlock):
            output.write(f'        <!-- block idx: {idx} -->\n')
            print("WARNING: Rendering notes with text in them is not yet supported. Layout will be incorrect.")
            draw_text(block, output, svg_doc_info, debug)
        else:
            if debug > 0:
                print(f'warning: not converting block: {block.__class__}')

    # Overlay the page with a clickable rect to flip pages
    output.write('\n')
    output.write('        <!-- clickable rect to flip pages -->\n')
    output.write(f'        <rect x="0" y="0" width="{svg_doc_info.width}" height="{svg_doc_info.height}" fill-opacity="0"/>\n')
    # Closing page group
    output.write('    </g>\n')
    # END notebook
    output.write('</svg>\n')


def draw_stroke(block: SceneLineItemBlock, output: TextIOWrapper, svg_doc_info: SvgDocInfo, debug: bool):
    if debug > 0:
        print('----SceneLineItemBlock')
    # a SceneLineItemBlock contains a stroke
    output.write(f'        <!-- SceneLineItemBlock item_id: {block.item.item_id} -->\n')

    # make sure the object is not empty
    if block.item.value is None:
        return
    
    # pull the CRDT item out of the block (the stroke in this case)
    item = block.item.value

    # initiate the pen
    pen = Pen.create(item.tool.value, item.color.value, item.thickness_scale)


    filter = ""
    if item.tool.name == 'MECHANICAL_PENCIL_2':
        filter = ' filter="url(#mechPencilTexture)" '
    elif item.tool.name ==  'PENCIL_2':
        filter = ' filter="url(#pencilTexture)" '

    # BEGIN stroke
    output.write(f'        <!-- Stroke tool: {item.tool.name} color: {item.color.name} ({item.color.value}) thickness_scale: {item.thickness_scale} -->\n')
    output.write('<g>')

    last_xpos = -1.
    last_ypos = -1.
    last_segment_width = 0
    # Iterate through the point to form a polyline
    for point_id, point in enumerate(item.points):
        # align the original position
        xpos = point.x + svg_doc_info.xpos_delta
        ypos = point.y + svg_doc_info.ypos_delta
        # stretch the original position
        # ratio = (svg_doc_info.height / svg_doc_info.width) / (1872 / 1404)
        # if ratio > 1:
        #    xpos = ratio * ((xpos * svg_doc_info.width) / 1404)
        #    ypos = (ypos * svg_doc_info.height) / 1872
        # else:
        #    xpos = (xpos * svg_doc_info.width) / 1404
        #    ypos = (1 / ratio) * (ypos * svg_doc_info.height) / 1872
        
        # start a new polyline
        if point_id % pen.segment_length == 0:
            segment_color = pen.get_segment_color(point.speed, point.direction, point.width, point.pressure, last_segment_width)
            segment_width = pen.get_segment_width(point.speed, point.direction, point.width, point.pressure, last_segment_width)
            segment_opacity = pen.get_segment_opacity(point.speed, point.direction, point.width, point.pressure, last_segment_width)
            # print(segment_color, segment_width, segment_opacity, pen.stroke_linecap)
            # UPDATE stroke
            output.write('"/>\n')
            output.write('        <polyline ' + filter)
            output.write(f'style="fill:none; stroke:{segment_color} ;stroke-width:{segment_width:.3f};opacity:{segment_opacity}" ')
            output.write(f'stroke-linecap="{pen.stroke_linecap}" stroke-linejoin="{pen.stroke_linejoin}" ')
            output.write('points="')

        if last_xpos != -1.:
            # Join to previous polyline segment
            output.write(f'{last_xpos:.3f},{last_ypos:.3f} ')
        
        # store the last position
        last_xpos = xpos
        last_ypos = ypos
        last_segment_width = segment_width

        # BEGIN and END polyline segment
        output.write(f'{xpos:.3f},{ypos:.3f} ')

    # END stroke
    output.write('" /></g>\n')


def draw_text(block: RootTextBlock, output, svg_doc_info, debug):
    if debug > 0:
        print('----RootTextBlock')
    # a RootTextBlock contains text
    output.write(f'        <!-- RootTextBlock item_id: {block.block_id} -->\n')

    # add some style to get readable text
    output.write('        <style>\n')
    output.write('            .default {\n')
    output.write('                font: 50px serif\n')
    output.write('            }\n')
    output.write('        </style>\n')

    text = block.value

    # doc = TextDocument.from_scene_item(block.value)
    # for p in doc.contents:
    #     print(p)

    # actual_text = ''.join([x.value for x in block.value.items if x.value is not None])
    # print(actual_text)

    for text_item in text.items.sequence_items():
        # BEGIN text
        # https://developer.mozilla.org/en-US/docs/Web/SVG/Element/text
        xpos = block.value.pos_x + svg_doc_info.width / 2
        ypos = block.value.pos_y + svg_doc_info.height / 2
        output.write(f'        <!-- TextItem item_id: {text_item.item_id} -->\n')
        if text_item.value.strip():
            output.write(f'        <text x="{xpos}" y="{ypos}" class="default">{text_item.text.strip()}</text>\n')


def get_limits(blocks):
    xmin = xmax = None
    ymin = ymax = None
    for block in blocks:
        if isinstance(block, SceneLineItemBlock):
            xmin_tmp, xmax_tmp, ymin_tmp, ymax_tmp = get_limits_stroke(block)
        # text blocks use a different xpos/ypos coordinate system
        #elif isinstance(block, RootTextBlock):
        #    xmin_tmp, xmax_tmp, ymin_tmp, ymax_tmp = get_limits_text(block)
        else:
            continue
        if xmin_tmp is None:
            continue
        if xmin is None or xmin > xmin_tmp:
            xmin = xmin_tmp
        if xmax is None or xmax < xmax_tmp:
            xmax = xmax_tmp
        if ymin is None or ymin > ymin_tmp:
            ymin = ymin_tmp
        if ymax is None or ymax < ymax_tmp:
            ymax = ymax_tmp
    return xmin, xmax, ymin, ymax


def get_limits_stroke(block):
    # make sure the object is not empty
    if block.item.value is None:
        return None, None, None, None
    xmin = xmax = None
    ymin = ymax = None
    for point in block.item.value.points:
        xpos, ypos = point.x, point.y
        if xmin is None or xmin > xpos:
            xmin = xpos
        if xmax is None or xmax < xpos:
            xmax = xpos
        if ymin is None or ymin > ypos:
            ymin = ypos
        if ymax is None or ymax < ypos:
            ymax = ypos
    return xmin, xmax, ymin, ymax


def get_limits_text(block):
    xmin = block.pos_x
    xmax = block.pos_x + block.width
    ymin = block.pos_y
    ymax = block.pos_y
    return xmin, xmax, ymin, ymax


def get_dimensions(blocks, debug):
    # get block limits
    xmin, xmax, ymin, ymax = get_limits(blocks)
    if debug > 0:
        print(f"xmin: {xmin} xmax: {xmax} ymin: {ymin} ymax: {ymax}")
    # {xpos,ypos} coordinates are based on the top-center point
    # of the doc **iff there are no text boxes**. When you add
    # text boxes, the xpos/ypos values change.
    xpos_delta = XPOS_SHIFT
    if xmin is not None and (xmin + XPOS_SHIFT) < 0:
        # make sure there are no negative xpos
        xpos_delta += -(xmin + XPOS_SHIFT)
    #ypos_delta = SCREEN_HEIGHT / 2
    ypos_delta = 0
    # adjust dimensions if needed
    width = int(math.ceil(max(SCREEN_WIDTH, xmax - xmin if xmin is not None and xmax is not None else 0)))
    height = int(math.ceil(max(SCREEN_HEIGHT, ymax - ymin if ymin is not None and ymax is not None else 0)))
    if debug > 0:
        print(f"height: {height} width: {width} xpos_delta: {xpos_delta} ypos_delta: {ypos_delta}")
    return SvgDocInfo(height=height, width=width, xpos_delta=xpos_delta, ypos_delta=ypos_delta)
