"""Safe deletion of uploaded files under the configured upload root."""

from pathlib import Path

from app.config import get_settings


def safe_remove_upload(path: str | Path, *, remove_parent: bool = False) -> None:
    """Unlink a stored upload only when it lives under the upload root.

    Cleanup is best-effort: failures are silent so they never block the
    surrounding delete operation.
    """
    upload_root = Path(get_settings().upload_dir).resolve()
    try:
        target = Path(path).resolve()
        if not target.is_relative_to(upload_root):
            return
        target.unlink(missing_ok=True)
        if remove_parent:
            try:
                target.parent.rmdir()
            except OSError:
                pass
    except OSError:
        pass
