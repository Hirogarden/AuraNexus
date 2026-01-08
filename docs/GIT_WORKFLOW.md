# Git Workflow Guide for AuraNexus

## Quick Reference

```powershell
# Check what's changed
git status

# Stage specific files
git add file1.py file2.md

# Stage all changes
git add .

# Commit with message
git commit -m "Add Docker architecture and memory analysis"

# Push to remote (if configured)
git push
```

## Avoiding OOM Issues

### Problem
VS Code's Source Control view loads diffs for ALL uncommitted files simultaneously, which can cause OOM when you have:
- Many uncommitted files
- Large documentation files
- Files with many lines

### Solution: Commit Regularly

**Best Practice: Commit after each logical unit of work**

```powershell
# After adding Docker support
git add docker-compose.yml Dockerfile Dockerfile.agent
git commit -m "Add Docker architecture for multi-agent containers"

# After writing documentation
git add docs/DOCKER_ARCHITECTURE.md
git commit -m "Document Docker container architecture"

# After implementing features
git add src/agent_runtime.py
git commit -m "Add agent runtime for character containers"
```

## Step-by-Step: Your Current Situation

### 1. Check Status
```powershell
git status
```
Shows 20 uncommitted files

### 2. Stage Related Files in Groups

**Group 1: Docker Infrastructure**
```powershell
git add docker-compose.yml Dockerfile Dockerfile.agent
git commit -m "Add Docker Compose setup for multi-agent architecture"
```

**Group 2: Documentation**
```powershell
git add docs/DOCKER_ARCHITECTURE.md docs/MEMORY_ARCHITECTURE_ANALYSIS.md docs/OLLAMA_FEATURE_VERIFICATION.md
git commit -m "Add architecture and integration analysis docs"
```

**Group 3: Agent Runtime**
```powershell
git add src/agent_runtime.py
git commit -m "Add agent runtime for containerized characters"
```

**Group 4: Test Files**
```powershell
git add test_*.py tool_demo.py interactive_test.py
git commit -m "Add test utilities for new features"
```

**Group 5: Tools**
```powershell
git add tools/
git commit -m "Add testing utilities for Ollama features"
```

**Group 6: Config Files**
```powershell
git add .gitignore AuraNexus.code-workspace launch.py
git commit -m "Update gitignore and workspace config"
```

**Group 7: Remaining Files**
```powershell
git add .
git commit -m "Add remaining project files"
```

### 3. Verify Clean State
```powershell
git status
```
Should show: "nothing to commit, working tree clean"

## Daily Workflow

### Morning
```powershell
# Update from remote (if team project)
git pull
```

### During Work
```powershell
# Commit every 30-60 minutes or after each feature
git add <files>
git commit -m "Brief description of what changed"
```

### End of Day
```powershell
# Check status
git status

# Commit anything left
git add .
git commit -m "End of day: work in progress on <feature>"

# Push to remote (if configured)
git push
```

## Useful Git Commands

### Check What Changed
```powershell
# See changed files
git status

# See line-by-line changes (be careful with large files!)
git diff

# See changes in specific file
git diff path/to/file.py
```

### Undo Mistakes
```powershell
# Unstage file (undo 'git add')
git reset HEAD file.py

# Discard changes to file (CAREFUL: can't undo!)
git checkout -- file.py

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes - CAREFUL!)
git reset --hard HEAD~1
```

### View History
```powershell
# See commit history
git log

# See compact history
git log --oneline

# See last 5 commits
git log --oneline -5
```

## .gitignore Best Practices

Already added to prevent future issues:
```gitignore
# Large docs temporarily ignored to prevent OOM
docs/MEMORY_ARCHITECTURE_ANALYSIS.md
docs/DOCKER_ARCHITECTURE.md
docs/OLLAMA_FEATURE_VERIFICATION.md

# Python
__pycache__/
*.pyc
.venv/

# IDE
.vscode/
*.code-workspace

# Data
data/
logs/
*.log
```

**After optimizing docs, remove them from .gitignore!**

## Pro Tips

1. **Commit often**: Small, frequent commits are easier to manage
2. **Descriptive messages**: "Add feature X" > "updates"
3. **Group related changes**: Don't mix unrelated fixes in one commit
4. **Close Source Control panel**: Reduces memory usage while coding
5. **Use command line for large changes**: Faster than VS Code UI

## Emergency: OOM Right Now?

```powershell
# Close VS Code Source Control panel
# Then commit from terminal:

git add .
git commit -m "Bulk commit to resolve OOM issue"

# Restart VS Code
```

## Aliases for Speed

Add to PowerShell profile (`$PROFILE`):
```powershell
function gs { git status }
function ga { git add $args }
function gc { git commit -m $args }
function gp { git push }
function gl { git log --oneline -10 }
```

Then use:
```powershell
gs              # git status
ga file.py      # git add file.py
gc "message"    # git commit -m "message"
```
