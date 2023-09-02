"""Export text content of rm files as Markdown."""

from rmscene.scene_items import ParagraphStyle
from rmscene.scene_stream import RootTextBlock
from rmscene.text import TextDocument


def print_text(blocks, fout):
    for block in blocks:
        if isinstance(block, RootTextBlock):        
            print("processing text block")
            doc = TextDocument.from_scene_item(block.value)

            for p in doc.contents:
                style = p.style.value
                line = str(p).strip()
                if line:
                    if style == ParagraphStyle.BULLET:
                        print("* " + line + "\n", file=fout)
                    elif style == ParagraphStyle.BULLET2:
                        print("  * " + line + "\n", file=fout)
                    elif style == ParagraphStyle.BOLD:
                        print("**" + line + "**\n", file=fout)
                    elif style == ParagraphStyle.HEADING:
                        print("# " + line + "\n", file=fout)
                    elif style == ParagraphStyle.PLAIN:
                        print(line + "\n", file=fout)
                    else:
                        print(("[unknown format %s] " % style) + line)
                else:
                    print(("[blank line %s] " % style) + line)
