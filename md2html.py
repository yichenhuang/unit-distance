#!/usr/bin/env python3
"""Convert a Markdown file with LaTeX math into a readable MathJax HTML file."""

import argparse
import html
import re
from pathlib import Path


def is_escaped(text, index):
    backslashes = 0
    i = index - 1
    while i >= 0 and text[i] == "\\":
        backslashes += 1
        i -= 1
    return backslashes % 2 == 1


def find_unescaped_dollar(text, start):
    i = start
    while i < len(text):
        if text[i] == "$" and not is_escaped(text, i) and not text.startswith("$$", i):
            return i
        i += 1
    return -1


def split_protected_spans(text):
    """Split out inline code and inline math before Markdown emphasis parsing."""
    spans = []
    start = 0
    i = 0

    def flush_text(end):
        if end > start:
            spans.append(("text", text[start:end]))

    while i < len(text):
        if text[i] == "`":
            end = text.find("`", i + 1)
            if end != -1:
                flush_text(i)
                spans.append(("code", text[i + 1 : end]))
                i = end + 1
                start = i
                continue

        if text.startswith(r"\(", i):
            end = text.find(r"\)", i + 2)
            if end != -1:
                flush_text(i)
                spans.append(("math", text[i : end + 2]))
                i = end + 2
                start = i
                continue

        if text[i] == "$" and not is_escaped(text, i) and not text.startswith("$$", i):
            end = find_unescaped_dollar(text, i + 1)
            if end != -1:
                flush_text(i)
                spans.append(("math", text[i : end + 1]))
                i = end + 1
                start = i
                continue

        i += 1

    flush_text(len(text))
    return spans


def apply_emphasis(text):
    text = re.sub(r"\*\*(?!\s)(.+?)(?<!\s)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\s|\*)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", text)
    return text


def render_inline(text):
    parts = []
    protected = {}
    for span_type, value in split_protected_spans(text):
        if span_type == "text":
            parts.append(html.escape(value, quote=False))
            continue

        placeholder = f"\u0000MD2HTML_PROTECTED_{len(protected)}\u0000"
        if span_type == "code":
            protected[placeholder] = f"<code>{html.escape(value)}</code>"
        elif span_type == "math":
            protected[placeholder] = html.escape(value, quote=False)
        parts.append(placeholder)

    rendered = apply_emphasis("".join(parts))
    for placeholder, replacement in protected.items():
        rendered = rendered.replace(placeholder, replacement)
    return rendered


def markdown_to_html(markdown_text):
    lines = markdown_text.splitlines()
    out = []
    paragraph = []
    i = 0

    def flush_paragraph():
        if paragraph:
            out.append(f"<p>{render_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
            continue

        if stripped in {"---", "***"}:
            flush_paragraph()
            out.append("<hr>")
            i += 1
            continue

        if stripped.startswith(r"\[") or stripped.startswith("$$"):
            flush_paragraph()
            closing = r"\]" if stripped.startswith(r"\[") else "$$"
            if len(stripped) > len(closing) and stripped.endswith(closing):
                out.append(f"<div class=\"math-block\">{html.escape(line)}</div>")
                i += 1
                continue

            block = [line]
            i += 1
            while i < len(lines):
                block.append(lines[i])
                if lines[i].strip().endswith(closing):
                    i += 1
                    break
                i += 1
            out.append(f"<div class=\"math-block\">{html.escape(chr(10).join(block))}</div>")
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            out.append(f"<h{level}>{render_inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{markdown_to_html(chr(10).join(quote))}</blockquote>")
            continue

        if re.match(r"^[-*]\s+", stripped):
            flush_paragraph()
            out.append("<ul>")
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i].strip()):
                item = re.sub(r"^[-*]\s+", "", lines[i].strip())
                out.append(f"<li>{render_inline(item)}</li>")
                i += 1
            out.append("</ul>")
            continue

        ordered_item_re = re.compile(r"^\d+[.)](?:\s+(.*)|\s*)$")
        if ordered_item_re.match(stripped):
            flush_paragraph()
            out.append("<ol>")
            while i < len(lines):
                current = lines[i].strip()
                item_match = ordered_item_re.match(current)
                if not item_match:
                    break

                item_lines = []
                first_line = item_match.group(1) or ""
                if first_line:
                    item_lines.append(first_line)
                i += 1

                while i < len(lines):
                    line = lines[i]
                    current = line.strip()

                    if ordered_item_re.match(current):
                        break

                    if not current:
                        next_i = i + 1
                        while next_i < len(lines) and not lines[next_i].strip():
                            next_i += 1
                        if next_i >= len(lines):
                            i = next_i
                            break
                        if ordered_item_re.match(lines[next_i].strip()):
                            i = next_i
                            break
                        if lines[next_i].startswith((" ", "\t")):
                            item_lines.append("")
                            i += 1
                            continue
                        break

                    if line.startswith((" ", "\t")):
                        item_lines.append(line.strip())
                        i += 1
                        continue

                    item_lines.append(line)
                    i += 1

                item_markdown = "\n".join(item_lines).strip()
                if not item_markdown:
                    out.append("<li></li>")
                elif "\n" in item_markdown:
                    out.append(f"<li>{markdown_to_html(item_markdown)}</li>")
                else:
                    out.append(f"<li>{render_inline(item_markdown)}</li>")
            out.append("</ol>")
            continue

        paragraph.append(line)
        i += 1

    flush_paragraph()
    return "\n".join(out)


def make_html(title, markdown_text):
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
        processEscapes: true
      }},
      svg: {{ fontCache: 'global' }}
    }};
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
  <style>
    body {{
      margin: 0;
      background: #f7f7f4;
      color: #1f2328;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.62;
    }}
    main {{
      max-width: 920px;
      margin: 0 auto;
      padding: 40px 28px 80px;
      background: #fff;
      min-height: 100vh;
      box-shadow: 0 0 0 1px #e4e4df;
    }}
    h1, h2, h3 {{ line-height: 1.25; margin-top: 1.7em; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 24px; border-bottom: 1px solid #e5e5e0; padding-bottom: 4px; }}
    h3 {{ font-size: 19px; }}
    p {{ margin: 0 0 1em; }}
    blockquote {{
      border-left: 4px solid #b8c4d6;
      margin: 1.2em 0;
      padding: 0.2em 1em;
      background: #f7f9fc;
    }}
    pre {{
      overflow-x: auto;
      background: #f2f2ee;
      padding: 12px;
      border-radius: 6px;
    }}
    code {{
      background: #f2f2ee;
      padding: 1px 4px;
      border-radius: 4px;
    }}
    pre code {{
      background: none;
      padding: 0;
    }}
    .math-block {{
      overflow-x: auto;
      margin: 1.1em 0;
      padding: 0.2em 0;
    }}
    mjx-container {{
      overflow-x: auto;
      overflow-y: hidden;
      max-width: 100%;
    }}
  </style>
</head>
<body>
<main>
  {markdown_to_html(markdown_text)}
</main>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown_file", help="Path to the Markdown file to render.")
    parser.add_argument(
        "--output",
        help="Output HTML path. Defaults to the input path with .html extension.",
    )
    parser.add_argument("--title", default="Rendered Markdown Output")
    args = parser.parse_args()

    markdown_path = Path(args.markdown_file)
    output_path = Path(args.output) if args.output else markdown_path.with_suffix(".html")

    markdown_text = markdown_path.read_text(encoding="utf-8")
    output_path.write_text(make_html(args.title, markdown_text), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
