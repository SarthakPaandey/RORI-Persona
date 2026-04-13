"""GitHub repository fetching and parsing service."""

import structlog
from dataclasses import dataclass
from typing import List

from github import Github

from app.config import Settings

logger = structlog.get_logger()


@dataclass
class RepoInfo:
    """Parsed repository information."""

    name: str
    description: str
    url: str
    language: str
    stars: int
    topics: List[str]
    readme_content: str
    tech_stack: List[str]
    last_updated: str
    pushed_at: str
    is_fork: bool


class GitHubService:
    """Fetches and parses GitHub repository information."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.github = Github(settings.github_token)
        self.username = settings.github_username

    def fetch_all_repos(self) -> List[RepoInfo]:
        """Fetch all public repositories for the user."""
        user = self.github.get_user(self.username)
        repos = []

        for repo in user.get_repos(type="public", sort="updated", direction="desc"):
            if repo.fork:
                continue

            try:
                repo_info = self._parse_repo(repo)
                repos.append(repo_info)
                logger.info("Fetched repo", name=repo.name)
            except Exception as e:
                logger.warning("Failed to parse repo", name=repo.name, error=str(e))

        logger.info("Total repos fetched", count=len(repos))
        return repos

    def _parse_repo(self, repo) -> RepoInfo:
        """Parse a GitHub repo into structured info."""
        readme_content = ""
        try:
            readme = repo.get_readme()
            readme_content = readme.decoded_content.decode("utf-8")
        except Exception:
            readme_content = "No README available."

        languages = list(repo.get_languages().keys())
        topics = repo.get_topics() or []
        tech_stack = self._detect_tech_stack(readme_content, languages) or []

        return RepoInfo(
            name=repo.name,
            description=repo.description or "No description",
            url=repo.html_url,
            language=repo.language or "Unknown",
            stars=repo.stargazers_count,
            topics=topics,
            readme_content=readme_content,
            tech_stack=tech_stack,
            last_updated=repo.updated_at.isoformat(),
            pushed_at=repo.pushed_at.isoformat() if repo.pushed_at else repo.updated_at.isoformat(),
            is_fork=repo.fork,
        )

    def _detect_tech_stack(self, readme: str, languages: List[str]) -> List[str]:
        """Detect technologies mentioned in README and languages."""
        tech_keywords = [
            "React",
            "Next.js",
            "Vue",
            "Angular",
            "Svelte",
            "Node.js",
            "Express",
            "FastAPI",
            "Django",
            "Flask",
            "PostgreSQL",
            "MongoDB",
            "Redis",
            "MySQL",
            "SQLite",
            "Docker",
            "Kubernetes",
            "AWS",
            "GCP",
            "Azure",
            "TensorFlow",
            "PyTorch",
            "LangChain",
            "OpenAI",
            "Pinecone",
            "ChromaDB",
            "Weaviate",
            "TypeScript",
            "Python",
            "Rust",
            "Go",
            "Java",
            "GraphQL",
            "REST",
            "gRPC",
            "Tailwind",
            "Material UI",
            "Chakra",
            "Vercel",
            "Railway",
            "Heroku",
            "Netlify",
            "GitHub Actions",
            "CI/CD",
            "Prisma",
            "SQLAlchemy",
            "Drizzle",
        ]

        detected = set(languages)
        readme_lower = readme.lower()

        for tech in tech_keywords:
            if tech.lower() in readme_lower:
                detected.add(tech)

        return sorted(list(detected))

    def format_repo_for_embedding(self, repo: RepoInfo) -> str:
        """Format a repo into a text document for embedding."""
        return f"""GitHub Repository: {repo.name}
URL: {repo.url}
Description: {repo.description}
Primary Language: {repo.language}
Tech Stack: {', '.join(repo.tech_stack)}
Topics: {', '.join(repo.topics)}
Stars: {repo.stars}
Last Code Push: {repo.pushed_at}
Last Updated: {repo.last_updated}

README:
{repo.readme_content[:3000]}

Technical Details:
- This project uses {', '.join(repo.tech_stack[:5])} as its core technologies.
- The repository is written primarily in {repo.language}.
"""
