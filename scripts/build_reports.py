"""Build public, static research reports from the accepted Markdown snapshots.

Requires Python 3 and Pandoc. Runtime pages do not need either program.
Source Markdown and aggregate JSON are copied unchanged; only HTML links adapt
the backend's paths to their public counterparts.
"""

from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EDITIONS = {
    "city_functions_research": "Срез 7 октября 2026: тепло, вода, лекарства, медицина, образование и расходы восстановления.",
    "bombing_effects_phase2": "Срез 6 октября 2026: три эпизода и проверка транспортного прогноза. Раздел городских функций расширен в отчёте от 7 октября.",
    "bombing_effects_research": "Первый разбор от 6 октября 2026. Сохранён как история исследования: позднее база сравнения проверена заново, а набор городских функций расширен. Числа разных версий нельзя смешивать.",
    "activity_index": "Описание тестового индекса поездок на 6 октября 2026. База относится к военному периоду; индекс не оценивает всю жизнь города или причинный эффект атак.",
}


def build():
    for stem, edition in EDITIONS.items():
        source = REPORTS / f"{stem}.md"
        title = source.read_text(encoding="utf-8").splitlines()[0].removeprefix("# ")
        result = subprocess.run([
            "pandoc", str(source), "--from=gfm", "--to=html5", "--standalone",
            "--toc", "--toc-depth=2", "--wrap=none", "--no-highlight",
            f"--template={REPORTS / 'report-template.html'}",
            f"--metadata=title:{title}", "--metadata=lang:ru",
            f"--variable=report-status:{edition}", f"--variable=source-file:{stem}.md",
        ], check=True, text=True, capture_output=True)
        html = result.stdout
        for other in EDITIONS:
            html = html.replace(f'href="{other}.md"', f'href="{other}.html"')
        html = html.replace('href="../data/research/expanded/public.json"', 'href="../research_data.json"')
        html = re.sub(r'href="../data/research/expanded/(results|protocol|manifest)\.json"',
                      r'href="data/expanded/\1.json"', html)
        html = html.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
        (REPORTS / f"{stem}.html").write_text(html, encoding="utf-8")
        print(f"reports/{stem}.html")


if __name__ == "__main__":
    build()
