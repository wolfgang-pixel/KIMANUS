# CLAUDE.md - AI Assistant Guide for KIMANUS

This document provides essential context for AI assistants working on the KIMANUS (KI-Manus Regional APP) project.

## Project Overview

**KIMANUS** is a regional application project. The name suggests integration with AI capabilities ("KI" = Künstliche Intelligenz / Artificial Intelligence).

### Current State

This project is in the **early initialization phase**. The repository currently contains only this documentation and a basic README.

## Repository Structure

```
KIMANUS/
├── README.md          # Project description
├── CLAUDE.md          # This file - AI assistant guide
└── (future directories will be documented as they are created)
```

## Development Guidelines

### Git Workflow

1. **Branch Naming**: Feature branches should follow the pattern `claude/<feature-name>-<session-id>` for AI-assisted development
2. **Commits**: Use clear, descriptive commit messages
3. **Main Branch**: The `main` branch contains stable code; develop on feature branches

### Code Standards (To Be Established)

As the project develops, document the following here:
- Programming language(s) and versions
- Code formatting and linting rules
- Testing requirements
- Documentation standards

## Commands Reference

### Git Commands

```bash
# Check current status
git status

# Create and push a new branch
git checkout -b <branch-name>
git push -u origin <branch-name>

# Standard commit workflow
git add <files>
git commit -m "descriptive message"
git push
```

### Build Commands

*To be added when build system is configured*

### Test Commands

*To be added when testing framework is set up*

## Architecture

*To be documented as the project architecture is defined*

### Key Components

*Document main modules and their responsibilities here*

### Data Flow

*Document how data moves through the application*

## Configuration

### Environment Variables

*List required environment variables when they are established*

### Configuration Files

*Document configuration files and their purposes*

## Dependencies

*List major dependencies and their purposes when package management is set up*

## Common Tasks for AI Assistants

### When Starting a New Feature

1. Review this CLAUDE.md for current conventions
2. Check the README.md for project context
3. Create a feature branch following naming conventions
4. Document significant changes in relevant documentation

### When Fixing Bugs

1. Understand the issue thoroughly
2. Write tests to reproduce the bug (when testing is set up)
3. Implement the fix
4. Verify the fix doesn't introduce regressions

### When Reviewing Code

1. Check for adherence to project conventions
2. Verify proper error handling
3. Ensure documentation is updated if needed
4. Look for potential security issues

## Important Notes

- **Security**: Never commit sensitive data (API keys, credentials, etc.)
- **Documentation**: Update this file and other docs when making significant changes
- **Testing**: Write tests for new functionality (once testing framework is established)

## Project-Specific Context

### Domain Knowledge

*Add domain-specific terminology and concepts as they become relevant*

### External Integrations

*Document any external services, APIs, or systems the project integrates with*

## Troubleshooting

### Common Issues

*Document common problems and their solutions as they are discovered*

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-04 | Initial CLAUDE.md created | AI Assistant |

---

*This document should be updated as the project evolves. AI assistants should check this file at the start of each session for the latest project conventions and context.*
