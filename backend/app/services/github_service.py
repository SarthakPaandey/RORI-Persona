"""GitHub repository fetching and parsing service."""

import structlog
from dataclasses import dataclass
from typing import List, Optional, Set

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

    def fetch_all_repos(
        self,
        showcase_repos: Optional[Set[str]] = None,
        exclude_repos: Optional[Set[str]] = None,
    ) -> List[RepoInfo]:
        """Fetch public repositories for the user.

        When *showcase_repos* is provided, **only** those repos (plus any with
        a description and real code) are ingested. Everything in *exclude_repos*
        is always skipped. Repos are sorted by most-recent code push so the
        latest projects surface first.
        """
        user = self.github.get_user(self.username)
        repos = []

        exclude = exclude_repos or set()

        for repo in user.get_repos(type="public", sort="pushed", direction="desc"):
            if repo.fork:
                continue
            if repo.name in exclude:
                logger.info("Skipped excluded repo", name=repo.name)
                continue

            # When a showcase list is provided, skip repos that are NOT in the
            # showcase AND look like trivial/empty repos (no language, tiny size,
            # no description).
            if showcase_repos and repo.name not in showcase_repos:
                is_meaningful = (
                    repo.language
                    and repo.size >= 50
                    and repo.description
                )
                if not is_meaningful:
                    logger.info(
                        "Skipped non-showcase trivial repo",
                        name=repo.name,
                        size=repo.size,
                        language=repo.language,
                    )
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
            "Kotlin",
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
            "Firebase",
            "Vapi",
            "ElevenLabs",
            "LangGraph",
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
