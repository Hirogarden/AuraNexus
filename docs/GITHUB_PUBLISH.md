# Publishing AuraNexus to GitHub

This document shows two approaches to publish this local repository to GitHub:

1) Quick (recommended): use the GitHub CLI (`gh`).

- Install `gh` and authenticate: https://cli.github.com/

  ```powershell
  gh auth login
  powershell -ExecutionPolicy Bypass -File scripts\publish_repo.ps1 -Name AuraNexus -Public
  ```

2) Manual steps (no `gh`):

  - Create a new empty repository on github.com (choose visibility).
  - Add the remote and push:

  ```powershell
  git init
  git add -A
  git commit -m "Initial commit: AuraNexus scaffold"
  git remote add origin git@github.com:<your-username>/AuraNexus.git
  git push -u origin main
  ```

Notes:
- The `scripts/publish_repo.ps1` helper will initialize git and create an initial commit if none exists.
- If you want me to run the publish commands for you, let me know and I can attempt to run them (I will ask for confirmation first).
