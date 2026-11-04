"""브라우저 단독 실행 페이지(demo/index.html)를 만든다.

template.html 에 분석 엔진(engine.js)과 샘플 데이터를 넣어 파일 하나로 묶는다.
설치 없이 index.html 을 더블클릭해서 열면 된다.

    python demo/build_demo.py            # demo/index.html + 루트 index.html (GitHub Pages)
    python demo/build_demo.py --fragment out.html   # <html>/<head> 없이 본문만 (호스팅용)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app import sample_cnc, sample_data  # noqa: E402

SAMPLES = [
    (sample_data, "경영지원팀 사무직",
     "가상의 경영지원팀 박지훈 대리의 메일 50건과 파일 80개입니다."),
    (sample_cnc, "공작기계 제어개발",
     "가상의 공작기계 회사 제어개발팀 정우진 책임연구원의 메일 50건과 파일 90개입니다. "
     "펌웨어 릴리스, 필드 불량, 고객사 채터링 이슈, EtherCAT 전환 프로젝트가 들어 있어요."),
]


def build() -> tuple[str, str]:
    template = (HERE / "template.html").read_text(encoding="utf-8")
    engine = (HERE / "engine.js").read_text(encoding="utf-8")
    samples = [{**mod.SAMPLE_OWNER, "label": label, "desc": desc, "mbox": mod.build_mbox(), "csv": mod.build_files_csv()}
               for mod, label, desc in SAMPLES]
    sample_js = json.dumps(samples, ensure_ascii=False).replace("</", "<\\/")
    page = template.replace("/*__ENGINE__*/", engine.replace("</script", "<\\/script")).replace(
        "/*__SAMPLE__*/null", sample_js)
    head, body = page.split("<!--BODY-->", 1)
    standalone = (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + head + "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )
    fragment = head + body
    return standalone, fragment


if __name__ == "__main__":
    standalone, fragment = build()
    if len(sys.argv) == 3 and sys.argv[1] == "--fragment":
        Path(sys.argv[2]).write_text(fragment, encoding="utf-8")
        print(f"{sys.argv[2]} 를 만들었습니다.")
    else:
        (HERE / "index.html").write_text(standalone, encoding="utf-8")
        # 저장소 루트의 index.html 은 GitHub Pages(https://dhkdch1999.github.io/task1/)의 첫 화면이다
        (HERE.parent / "index.html").write_text(standalone, encoding="utf-8")
        print("demo/index.html 과 루트 index.html(GitHub Pages 첫 화면)을 만들었습니다.")
