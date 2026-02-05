#!/usr/bin/env python3
"""
GitHub Sync - Analysis Results Synchronization

Syncs audio analysis results to GitHub repository for:
- Version control of analysis data
- Access from Claude Code for further analysis
- Cross-device synchronization
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

from rich.console import Console
from rich.panel import Panel

console = Console()


class GitHubSync:
    """Synchronize analysis results to GitHub repository"""

    def __init__(
        self,
        repo_path: Optional[str] = None,
        results_subdir: str = "stem-separator/analysis-results"
    ):
        """
        Initialize GitHub sync.

        Args:
            repo_path: Path to local git repository (default: ~/.github)
            results_subdir: Subdirectory within repo for results
        """
        if repo_path:
            self.repo_path = Path(repo_path).expanduser().resolve()
        else:
            self.repo_path = Path.home() / ".github"

        self.results_dir = self.repo_path / results_subdir
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def sync_results(
        self,
        output_dir: Path,
        branch: str = "analysis-results",
        commit_message: Optional[str] = None,
        push: bool = True
    ) -> bool:
        """
        Sync analysis results to GitHub.

        Args:
            output_dir: Directory containing processing results
            branch: Git branch to use
            commit_message: Custom commit message
            push: Whether to push to remote

        Returns:
            True if sync successful
        """
        output_dir = Path(output_dir)

        if not output_dir.exists():
            console.print(f"[red]Output directory not found: {output_dir}[/red]")
            return False

        console.print(Panel.fit(
            f"[bold]GitHub Sync[/bold]\n\n"
            f"Source: [cyan]{output_dir}[/cyan]\n"
            f"Repo: [cyan]{self.repo_path}[/cyan]\n"
            f"Branch: [cyan]{branch}[/cyan]",
            border_style="blue"
        ))

        try:
            # 1. Ensure we're on the correct branch
            self._ensure_branch(branch)

            # 2. Copy results to repo
            session_name = output_dir.name
            dest_dir = self.results_dir / session_name
            self._copy_results(output_dir, dest_dir)

            # 3. Create/update index
            self._update_index()

            # 4. Git add, commit, push
            if commit_message is None:
                commit_message = f"Add analysis results: {session_name}"

            self._git_commit(commit_message)

            if push:
                self._git_push(branch)

            console.print("[green]Sync complete![/green]")
            return True

        except Exception as e:
            console.print(f"[red]Sync failed: {e}[/red]")
            return False

    def _ensure_branch(self, branch: str):
        """Ensure we're on the correct git branch"""
        os.chdir(self.repo_path)

        # Check if branch exists
        result = subprocess.run(
            ["git", "branch", "--list", branch],
            capture_output=True,
            text=True,
            cwd=self.repo_path
        )

        if branch not in result.stdout:
            # Create branch
            console.print(f"Creating branch: {branch}")
            subprocess.run(
                ["git", "checkout", "-b", branch],
                cwd=self.repo_path,
                check=True
            )
        else:
            # Switch to branch
            subprocess.run(
                ["git", "checkout", branch],
                cwd=self.repo_path,
                check=True
            )

    def _copy_results(self, source: Path, dest: Path):
        """Copy analysis results to repository"""
        dest.mkdir(parents=True, exist_ok=True)

        # Files/directories to copy
        items_to_copy = [
            "analysis",      # JSON analysis files
            "advice",        # AI advice markdown
            "metadata.json", # Metadata if exists
        ]

        copied_count = 0

        for item in items_to_copy:
            source_item = source / item

            if source_item.exists():
                dest_item = dest / item

                if source_item.is_dir():
                    if dest_item.exists():
                        shutil.rmtree(dest_item)
                    shutil.copytree(source_item, dest_item)
                    copied_count += len(list(source_item.iterdir()))
                else:
                    shutil.copy2(source_item, dest_item)
                    copied_count += 1

        # Create metadata if not exists
        metadata_file = dest / "metadata.json"
        if not metadata_file.exists():
            metadata = self._create_metadata(source, dest)
            metadata_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
            copied_count += 1

        console.print(f"Copied {copied_count} items to {dest}")

    def _create_metadata(self, source: Path, dest: Path) -> Dict[str, Any]:
        """Create metadata for the analysis session"""
        metadata = {
            "session_name": source.name,
            "sync_date": datetime.now().isoformat(),
            "source_path": str(source),
            "files": {}
        }

        # List analysis files
        analysis_dir = dest / "analysis"
        if analysis_dir.exists():
            for f in analysis_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    metadata["files"][f.stem] = {
                        "type": "analysis",
                        "keys": list(data.keys()) if isinstance(data, dict) else "array"
                    }
                except Exception:
                    pass

        # List advice files
        advice_dir = dest / "advice"
        if advice_dir.exists():
            for f in advice_dir.glob("*.md"):
                metadata["files"][f.stem] = {
                    "type": "advice",
                    "size": f.stat().st_size
                }

        return metadata

    def _update_index(self):
        """Update the index file listing all analysis sessions"""
        index_file = self.results_dir / "index.json"

        # Load existing index or create new
        if index_file.exists():
            index = json.loads(index_file.read_text())
        else:
            index = {
                "title": "Stem Separator Analysis Results",
                "updated": None,
                "sessions": []
            }

        # Scan for sessions
        sessions = []
        for session_dir in sorted(self.results_dir.iterdir()):
            if session_dir.is_dir() and not session_dir.name.startswith("."):
                metadata_file = session_dir / "metadata.json"

                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                else:
                    metadata = {"session_name": session_dir.name}

                sessions.append({
                    "name": session_dir.name,
                    "path": str(session_dir.relative_to(self.results_dir)),
                    "sync_date": metadata.get("sync_date", "unknown"),
                    "files_count": len(list(session_dir.rglob("*")))
                })

        index["sessions"] = sessions
        index["updated"] = datetime.now().isoformat()
        index["total_sessions"] = len(sessions)

        index_file.write_text(json.dumps(index, indent=2, ensure_ascii=False))
        console.print(f"Updated index: {len(sessions)} sessions")

    def _git_commit(self, message: str):
        """Stage and commit changes"""
        # Add all changes in results directory
        subprocess.run(
            ["git", "add", str(self.results_dir)],
            cwd=self.repo_path,
            check=True
        )

        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=self.repo_path
        )

        if result.stdout.strip():
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                check=True
            )
            console.print(f"Committed: {message}")
        else:
            console.print("[yellow]No changes to commit[/yellow]")

    def _git_push(self, branch: str, retries: int = 4):
        """Push to remote with retry logic"""
        delays = [2, 4, 8, 16]

        for attempt in range(retries):
            try:
                subprocess.run(
                    ["git", "push", "-u", "origin", branch],
                    cwd=self.repo_path,
                    check=True,
                    capture_output=True
                )
                console.print(f"[green]Pushed to origin/{branch}[/green]")
                return
            except subprocess.CalledProcessError as e:
                if attempt < retries - 1:
                    delay = delays[attempt]
                    console.print(f"[yellow]Push failed, retrying in {delay}s...[/yellow]")
                    import time
                    time.sleep(delay)
                else:
                    console.print(f"[red]Push failed after {retries} attempts[/red]")
                    raise

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all synced analysis sessions"""
        index_file = self.results_dir / "index.json"

        if index_file.exists():
            index = json.loads(index_file.read_text())
            return index.get("sessions", [])

        # Fallback: scan directory
        sessions = []
        for session_dir in sorted(self.results_dir.iterdir()):
            if session_dir.is_dir() and not session_dir.name.startswith("."):
                sessions.append({
                    "name": session_dir.name,
                    "path": str(session_dir)
                })

        return sessions

    def get_session(self, session_name: str) -> Optional[Path]:
        """Get path to a specific session"""
        session_path = self.results_dir / session_name

        if session_path.exists():
            return session_path

        return None


# Convenience function for direct import
def sync_results(
    output_dir: Path,
    branch: str = "analysis-results",
    repo_path: Optional[str] = None
) -> bool:
    """
    Convenience function to sync results.

    Args:
        output_dir: Directory containing processing results
        branch: Git branch to use
        repo_path: Path to git repository (default: ~/.github)

    Returns:
        True if sync successful
    """
    syncer = GitHubSync(repo_path=repo_path)
    return syncer.sync_results(output_dir, branch=branch)


def main():
    """CLI for GitHub sync"""
    import click

    @click.command()
    @click.argument("output_dir", type=click.Path(exists=True))
    @click.option("--branch", "-b", default="analysis-results", help="Git branch")
    @click.option("--repo", "-r", help="Repository path")
    @click.option("--no-push", is_flag=True, help="Don't push to remote")
    def sync(output_dir, branch, repo, no_push):
        """Sync analysis results to GitHub"""
        syncer = GitHubSync(repo_path=repo)
        syncer.sync_results(
            Path(output_dir),
            branch=branch,
            push=not no_push
        )

    @click.command()
    @click.option("--repo", "-r", help="Repository path")
    def list_sessions(repo):
        """List all synced sessions"""
        syncer = GitHubSync(repo_path=repo)
        sessions = syncer.list_sessions()

        if sessions:
            console.print("\n[bold]Synced Sessions:[/bold]\n")
            for session in sessions:
                console.print(f"  - {session['name']}")
        else:
            console.print("[yellow]No sessions found[/yellow]")

    # Create CLI group
    @click.group()
    def cli():
        """GitHub Sync for Stem Separator"""
        pass

    cli.add_command(sync)
    cli.add_command(list_sessions, name="list")

    cli()


if __name__ == "__main__":
    main()
