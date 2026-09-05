"""SQLAlchemy models for CodeLens persistence.

Schema supports three analysis entry points:
- OAuth users (manual analyze from the web UI)
- GitHub App webhooks (auto-analyze on pull_request events)
- GitHub Checks + PR comments (surfacing results back on github.com)
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """GitHub OAuth user who signed into the CodeLens web app."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    github_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    login: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    access_token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reports: Mapped[list["PrReport"]] = relationship(back_populates="user")
    review_posts: Mapped[list["PrReviewPost"]] = relationship(back_populates="user")


class GitHubInstallation(Base):
    """GitHub App installation — enables webhooks, Checks API, and PR comments without a logged-in user.

    One row per GitHub App install (org or user account). Installation access tokens are cached
    in memory by ``github_app`` service; only metadata is persisted here for production auditability.
    """

    __tablename__ = "github_installations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    installation_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    account_login: Mapped[str] = mapped_column(String(255), index=True)
    account_type: Mapped[str] = mapped_column(String(64), default="Organization")
    repository_selection: Mapped[str] = mapped_column(String(32), default="all")
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    repositories: Mapped[list["RegisteredRepository"]] = relationship(back_populates="installation")
    reports: Mapped[list["PrReport"]] = relationship(back_populates="installation")
    check_runs: Mapped[list["PrCheckRun"]] = relationship(back_populates="installation")


class RegisteredRepository(Base):
    """Repository visible to a GitHub App installation (synced from webhook events).

    Used to know which repos should receive auto-analysis and Checks without scanning all of GitHub.
    """

    __tablename__ = "registered_repositories"
    __table_args__ = (
        UniqueConstraint("installation_id", "full_name", name="uq_installation_repo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    installation_id: Mapped[int] = mapped_column(ForeignKey("github_installations.id"), index=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    repo: Mapped[str] = mapped_column(String(255), index=True)
    full_name: Mapped[str] = mapped_column(String(512), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    installation: Mapped["GitHubInstallation"] = relationship(back_populates="repositories")


class PrReport(Base):
    """Cached PR analysis report (JSON blob from ``AnalysisReport.to_dict()``)."""

    __tablename__ = "pr_reports"
    __table_args__ = (UniqueConstraint("owner", "repo", "pr_number", name="uq_pr_report"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    installation_id: Mapped[int | None] = mapped_column(
        ForeignKey("github_installations.id"), nullable=True, index=True
    )
    owner: Mapped[str] = mapped_column(String(255), index=True)
    repo: Mapped[str] = mapped_column(String(255), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(512))
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="oauth")
    report_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User | None"] = relationship(back_populates="reports")
    installation: Mapped["GitHubInstallation | None"] = relationship(back_populates="reports")
    check_runs: Mapped[list["PrCheckRun"]] = relationship(back_populates="report")
    review_posts: Mapped[list["PrReviewPost"]] = relationship(back_populates="report")


class WebhookDelivery(Base):
    """Audit + idempotency log for GitHub webhook deliveries (production-safe replay protection)."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    repository: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PrCheckRun(Base):
    """GitHub Check Run created for a PR head commit — links analysis to the Checks UI on github.com."""

    __tablename__ = "pr_check_runs"
    __table_args__ = (
        UniqueConstraint("owner", "repo", "pr_number", "head_sha", name="uq_pr_check_run"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    installation_id: Mapped[int] = mapped_column(ForeignKey("github_installations.id"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("pr_reports.id"), nullable=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    repo: Mapped[str] = mapped_column(String(255), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    head_sha: Mapped[str] = mapped_column(String(64), index=True)
    check_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conclusion: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    installation: Mapped["GitHubInstallation"] = relationship(back_populates="check_runs")
    report: Mapped["PrReport | None"] = relationship(back_populates="check_runs")


class PrReviewPost(Base):
    """Record of a summary comment posted back to GitHub (avoids duplicate spam on re-analyze)."""

    __tablename__ = "pr_review_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("pr_reports.id"), nullable=True)
    owner: Mapped[str] = mapped_column(String(255), index=True)
    repo: Mapped[str] = mapped_column(String(255), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    github_comment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_type: Mapped[str] = mapped_column(String(32), default="issue_comment")
    body_preview: Mapped[str | None] = mapped_column(String(512), nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User | None"] = relationship(back_populates="review_posts")
    report: Mapped["PrReport | None"] = relationship(back_populates="review_posts")
