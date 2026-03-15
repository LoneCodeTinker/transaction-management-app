"""
Automated SQLite database backup service using APScheduler.

Provides scheduled backup of orders_tracking.db with automatic rotation.
Keep only the latest 10 backups to manage disk space.
"""

import shutil
import os
import logging
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# Backup configuration
BACKUP_DIR = Path("backups")
DB_FILE = Path("orders_tracking.db")
BACKUP_RETENTION = 10  # Keep only the latest 10 backups


def create_backup_directory():
    """Ensure backup directory exists."""
    BACKUP_DIR.mkdir(exist_ok=True)


def get_backup_filename():
    """Generate backup filename with timestamp: orders_tracking_YYYYMMDD_HHMM.db"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    return f"orders_tracking_{timestamp}.db"


def backup_database():
    """
    Backup the SQLite database file and maintain rotation.
    
    - Copies orders_tracking.db to backups/ directory
    - Maintains only latest 10 backups
    - Logs all operations to backup.log
    """
    try:
        create_backup_directory()
        
        # Check if database file exists
        if not DB_FILE.exists():
            logger.warning(f"Database file {DB_FILE} not found. Skipping backup.")
            return
        
        # Create backup with timestamp
        backup_filename = get_backup_filename()
        backup_path = BACKUP_DIR / backup_filename
        
        # Copy database file
        shutil.copy2(str(DB_FILE), str(backup_path))
        logger.info(f"✓ Database backed up: {backup_path}")
        
        # Clean up old backups (keep only latest 10)
        cleanup_old_backups()
        
    except Exception as e:
        logger.error(f"✗ Backup failed: {e}")


def cleanup_old_backups():
    """
    Remove old backup files, keeping only the latest BACKUP_RETENTION files.
    
    Backup files are sorted by creation time and oldest ones are deleted.
    """
    try:
        # Get all backup files sorted by creation time (newest first)
        backup_files = sorted(
            BACKUP_DIR.glob("orders_tracking_*.db"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # If we have more than retention limit, delete oldest
        if len(backup_files) > BACKUP_RETENTION:
            for old_backup in backup_files[BACKUP_RETENTION:]:
                try:
                    old_backup.unlink()
                    logger.info(f"✓ Removed old backup: {old_backup.name}")
                except Exception as e:
                    logger.error(f"✗ Failed to remove backup {old_backup.name}: {e}")
    
    except Exception as e:
        logger.error(f"✗ Cleanup failed: {e}")


def start_scheduler():
    """
    Start the APScheduler background scheduler.
    
    - Runs backup_database() every 6 hours
    - Also runs once immediately on startup
    Returns:
        BackgroundScheduler instance
    """
    scheduler = BackgroundScheduler()
    
    # Schedule backup every 6 hours
    scheduler.add_job(
        backup_database,
        'interval',
        hours=6,
        id='database_backup',
        name='Database Backup Task',
        replace_existing=True
    )
    
    # Run backup immediately on startup
    try:
        backup_database()
    except Exception as e:
        logger.error(f"Initial backup on startup failed: {e}")
    
    # Start the scheduler
    scheduler.start()
    logger.info("✓ Backup scheduler started (runs every 6 hours)")
    
    return scheduler
