"""Routes for the public pages: home, resources and the user manual."""
import os
import re
from pathlib import Path

from flask import current_app, render_template, url_for

from . import bp
from .manual import render_manual

_YOUTUBE = re.compile(r"^https://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{6,20})")
_VIMEO = re.compile(r"^https://(?:www\.)?vimeo\.com/(\d+)")


def video_info():
    """The project video from the VIDEO_URL environment variable: link and embeddable URL (or None)."""
    link = os.environ.get("VIDEO_URL", "").strip()
    if not link.startswith("https://"):
        return {"link": None, "embed": None}
    match = _YOUTUBE.match(link)
    if match:
        return {"link": link, "embed": f"https://www.youtube-nocookie.com/embed/{match.group(1)}"}
    match = _VIMEO.match(link)
    if match:
        return {"link": link, "embed": f"https://player.vimeo.com/video/{match.group(1)}"}
    return {"link": link, "embed": None}


def published_doc(filename):
    """URL of a file in static/docs, or None while the file has not been published."""
    if (Path(current_app.static_folder) / "docs" / filename).is_file():
        return url_for("static", filename=f"docs/{filename}")
    return None


@bp.route("/")
def index():
    """Public landing page. After logging in, each role goes to its own home (see auth.login)."""
    return render_template("main/index.html", video=video_info(), final_report=published_doc("Final_Report.pdf"))


@bp.route("/resources")
def resources():
    """Public list of the project resources (reports, evidence, repository, manual and video)."""
    docs = {
        "final_report": published_doc("Final_Report.pdf"),
        "report1": published_doc("Activity1_Technical_Report.pdf"),
        "report2": published_doc("Activity2_System_Report.pdf"),
        "blog": published_doc("RL_Blog.docx"),
    }
    return render_template("main/resources.html", docs=docs, video=video_info())


@bp.route("/manual")
def manual():
    """The user manual as a readable web page."""
    title, html = render_manual(lambda name: url_for("static", filename=name))
    return render_template("main/manual.html", title=title, html=html)
