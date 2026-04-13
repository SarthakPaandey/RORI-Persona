"""Resume PDF parsing service."""

import structlog
from pathlib import Path
from typing import List

from pypdf import PdfReader

logger = structlog.get_logger()


class ResumeService:
    """Parses resume PDF into structured text."""

    def __init__(self, resume_path: str = "data/resume.pdf"):
        self.resume_path = Path(resume_path)

    def parse_resume(self) -> str:
        """Parse resume PDF into text."""
        if not self.resume_path.exists():
            logger.error("Resume file not found", path=str(self.resume_path))
            raise FileNotFoundError(f"Resume not found at {self.resume_path}")

        reader = PdfReader(str(self.resume_path))
        text_parts = []

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text_parts.append(text)
                logger.info("Parsed resume page", page=page_num + 1)

        full_text = "\n\n".join(text_parts)
        logger.info("Resume parsed", total_chars=len(full_text))

        return full_text

    def parse_resume_sections(self) -> List[dict]:
        """Parse resume into labeled sections for better retrieval."""
        full_text = self.parse_resume()

        section_headers = [
            "education",
            "experience",
            "work experience",
            "projects",
            "skills",
            "technical skills",
            "certifications",
            "publications",
            "awards",
            "summary",
            "objective",
            "contact",
        ]

        sections = []
        current_section = "header"
        current_content = []

        for line in full_text.split("\n"):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()

            is_header = any(
                line_lower == header or line_lower.startswith(header + ":")
                for header in section_headers
            )

            if is_header and current_content:
                sections.append(
                    {
                        "section": current_section,
                        "content": "\n".join(current_content).strip(),
                    }
                )
                current_section = line_stripped
                current_content = []
            else:
                if line_stripped:
                    current_content.append(line_stripped)

        if current_content:
            sections.append(
                {
                    "section": current_section,
                    "content": "\n".join(current_content).strip(),
                }
            )

        logger.info("Resume sections parsed", count=len(sections))
        return sections
