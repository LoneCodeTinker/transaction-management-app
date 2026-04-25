# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.
This project follows Semantic Versioning.

---

## [2.0.0] - 2026-03-03

### 🚀 Major Changes
- Migrated database from Excel-based storage to SQLite
- Refactored data access layer to support relational database structure
- Renamed application (core functionality preserved)

### ⚡ Improvements
- Improved performance and scalability
- Better data integrity and reliability
- Reduced external file dependency risks

### ❌ Removed
- Excel database support
- Excel-specific libraries and logic

### ⚠️ Breaking Changes
- Existing Excel database files are no longer supported
- Manual data migration required