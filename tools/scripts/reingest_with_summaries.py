#!/usr/bin/env python
"""Re-ingest the Maji Ndogo project with LLM-generated summaries."""

import asyncio
import logging
from pathlib import Path

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ltt.models import (
    CommentModel,
    DependencyModel,
    LearnerTaskProgressModel,
    LearningObjectiveModel,
    StatusSummaryModel,
    SubmissionModel,
    TaskModel,
    ValidationModel,
)
from ltt.services.ingest import ingest_project_file

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://ltt_user:ltt_password@localhost:5432/ltt_dev"

PROJECT_FILE = Path("project_data/DA/MN_Part1/structured/water_analysis_project.json")


async def clear_database(session: AsyncSession) -> None:
    """Clear all data from the database in the correct order."""
    logger.info("Clearing existing data...")

    # Delete in order to avoid FK violations
    await session.execute(delete(ValidationModel))
    await session.execute(delete(SubmissionModel))
    await session.execute(delete(CommentModel))
    await session.execute(delete(StatusSummaryModel))
    await session.execute(delete(LearnerTaskProgressModel))
    await session.execute(delete(DependencyModel))
    await session.execute(delete(LearningObjectiveModel))
    await session.execute(delete(TaskModel))

    await session.commit()
    logger.info("Database cleared.")


async def main() -> None:
    """Main entry point."""
    # Create engine and session
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Clear existing data
        await clear_database(session)

        # Ingest project with LLM summaries
        logger.info(f"Ingesting project from {PROJECT_FILE}...")
        logger.info("LLM summarization enabled - this may take a few minutes...")

        result = await ingest_project_file(
            session=session,
            file_path=PROJECT_FILE,
            dry_run=False,
            use_llm_summaries=True,  # Enable LLM summarization
        )

        logger.info(f"Ingestion complete!")
        logger.info(f"  Project ID: {result.project_id}")
        logger.info(f"  Tasks created: {result.task_count}")
        logger.info(f"  Objectives created: {result.objective_count}")

        if result.errors:
            logger.warning(f"  Errors: {result.errors}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
