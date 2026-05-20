from __future__ import annotations

from pathlib import Path


class JarvisFileGen:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def resolve_output_path(self, filename: str) -> Path:
        path = Path(filename).expanduser()
        if path.is_absolute():
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        target = self.output_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def write_pdf(self, filename: str, title: str, sections: list[tuple[str, str]]) -> str:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
        except Exception as exc:
            return f"ReportLab nao instalado. Instale reportlab para gerar PDF: {exc}"

        path = self.resolve_output_path(filename if filename.lower().endswith(".pdf") else f"{filename}.pdf")
        styles = getSampleStyleSheet()
        styles["Title"].textColor = colors.HexColor("#D89B20")
        styles["Heading2"].textColor = colors.HexColor("#C47A00")
        doc = SimpleDocTemplate(str(path), pagesize=A4)
        story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
        for heading, body in sections:
            story.append(Paragraph(heading, styles["Heading2"]))
            story.append(Paragraph(body.replace("\n", "<br/>"), styles["BodyText"]))
            story.append(Spacer(1, 10))
        doc.build(story)
        return f"PDF criado em: {path}"

