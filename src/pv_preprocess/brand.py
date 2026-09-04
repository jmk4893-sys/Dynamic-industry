"""회사 마크 — 도형과 색의 **단일 출처**.

`symbol_100x100mm.ai` 에서 직접 뽑았다. 눈으로 따라 그린 것이 아니다 — AI 파일은
PDF 1.4 컨테이너라 콘텐츠 스트림에 경로 연산자(`m`·`l`·`c`·`h`)가 그대로 들어 있고,
`tools/extract_brand.py` 가 그것을 해석해 절대좌표로 만든 뒤 PDF 좌표계(y 위)를
SVG 좌표계(y 아래)로 뒤집고 ArtBox 기준 0…100 으로 정규화한다. 이 파일의 `d`
문자열은 그 출력이며, **사람이 손으로 고치는 값이 아니다** — 아트워크가 바뀌면
추출을 다시 돌린다.

**색도 흉내내지 않았다.** 원본은 ICCBased 4성분(CMYK)이라 RGB 로 옮기려면 프로파일
변환이 필요한데, 그 변환식을 여기서 다시 쓰면 뷰어마다 다른 값이 나온다. 그래서
원본을 1,200 px 로 래스터화해 **실제 화면 픽셀에서 색을 읽었다**. CMYK 원값은
인쇄·도장 발주용으로 같이 남긴다.

## 왜 한 곳인가

마크가 3D 외장에도 붙고 콘솔 화면에도 붙는다. 두 벌로 두면 한쪽만 고쳐지는 날이
반드시 오고, 그날 두 마크는 같은 회사 것이 아니게 된다. 그래서 경로 문자열은 여기
한 곳에만 있고, 3D 캔버스 텍스처와 콘솔 SVG 가 **같은 문자열을 받아 쓴다** —
캔버스 `Path2D` 가 SVG 경로 문법을 그대로 먹기 때문에 가능하다. 두 소비자가 같은
도형을 쓰는지는 시험이 강제한다.

정확도는 `tools/check_brand_fidelity.mjs` 가 잰다 — 이 경로들을 브라우저로
래스터화해 원본 PDF 래스터와 픽셀 단위로 대조한다.
"""

from __future__ import annotations

from dataclasses import dataclass

#: 원본 아트워크. 재추출은 `python tools/extract_brand.py <파일>`.
SOURCE_FILE = "symbol_100x100mm.ai"

#: 그 아트워크가 저장소에서 있는 자리. 추출과 픽셀 대조를 아무나 다시 돌릴 수
#: 있어야 하므로 원본 자체를 저장소에 둔다 — 여기 없으면 `brand.py` 가 어디서
#: 나왔는지 확인할 길이 사라진다.
SOURCE_PATH = "assets/brand/" + SOURCE_FILE

#: 원본 ArtBox (pt) 와 실치수 (mm). 파일 이름의 100 mm 와 맞는다.
ARTBOX_PT: tuple[float, float, float, float] = (155.905, 294.843, 439.37, 547.047)
WIDTH_MM = 100.0002
HEIGHT_MM = 88.972

#: 정규화 viewBox — 폭을 100 으로 두고 높이는 원본 비율에서 나온다.
VIEW_W = 100.0
VIEW_H = 88.9718

#: 화면 색 — 원본 래스터에서 실측했다 (변환식으로 만든 값이 아니다).
BLUE = "#228CC9"
AMBER = "#FECA4A"

#: 인쇄·도장용 CMYK 원값.
BLUE_CMYK: tuple[float, float, float, float] = (0.776, 0.342, 0.016, 0.0)
AMBER_CMYK: tuple[float, float, float, float] = (0.0, 0.212, 0.815, 0.0)

ROLE_COLOUR: dict[str, str] = {"blue": BLUE, "amber": AMBER}


@dataclass(frozen=True)
class Shape:
    """마크를 이루는 채움 경로 하나."""

    tag: str
    role: str          # 'blue' | 'amber'
    d: str             # SVG 경로 — 캔버스 Path2D 도 같은 문자열을 먹는다
    cmyk: tuple[float, float, float, float]

    @property
    def colour(self) -> str:
        return ROLE_COLOUR[self.role]


#: 원본 콘텐츠 스트림의 채움 순서 그대로. 순서를 바꾸면 겹침이 달라진다.
SHAPES: tuple[Shape, ...] = (
    Shape(
        "blue-1",
        "blue",
        "M8.8425 30.8125L1.1848 44.0762C-0.3946 46.812 -0.3946 50.1824 "
        "1.1852 52.9182L15.6497 77.9721L25.8598 60.2874Z",
        (0.776, 0.342, 0.016, 0.0),
    ),
    Shape(
        "blue-2",
        "blue",
        "M36.0704 42.6023L19.0532 13.1274L12.2463 24.9173L29.2636 "
        "54.3921Z",
        (0.776, 0.342, 0.016, 0.0),
    ),
    Shape(
        "blue-3",
        "blue",
        "M46.2807 24.9174L38.7016 11.7898L25.088 11.7898L39.4739 "
        "36.7072Z",
        (0.776, 0.342, 0.016, 0.0),
    ),
    Shape(
        "blue-4",
        "blue",
        "M19.053 83.8666L19.4482 84.551C21.0279 87.2868 23.9468 88.972 "
        "27.1055 88.972L72.8953 88.972C76.0541 88.972 78.9733 87.2868 "
        "80.5527 84.551L95.0173 59.4971L33.1204 59.4971Z",
        (0.776, 0.342, 0.016, 0.0),
    ),
    Shape(
        "amber-1",
        "amber",
        "M98.8154 44.076L75.9206 4.421C74.3412 1.6852 71.4219 0.0 "
        "68.2632 0.0L50.001 0.0004L50.001 0.0L33.8946 0.0L42.0532 "
        "4.7103L70.2821 53.6045L98.4203 53.6024L98.8154 "
        "52.918C100.3948 50.1822 100.3948 46.8118 98.8154 44.076Z",
        (0.0, 0.212, 0.815, 0.0),
    ),
)


def shapes_of(role: str) -> tuple[Shape, ...]:
    return tuple(s for s in SHAPES if s.role == role)


def path_data() -> tuple[str, ...]:
    """경로 문자열만 — 소비자가 받아 쓰는 값."""
    return tuple(s.d for s in SHAPES)


def svg_paths(indent: str = "") -> str:
    """<path> 요소들. 콘솔 SVG 와 도면이 이것을 그대로 받는다."""
    return "\n".join(
        f'{indent}<path fill="{s.colour}" d="{s.d}"/>' for s in SHAPES)


def svg(size: int = 100, title: str = "회사 마크") -> str:
    """독립 SVG 한 장."""
    height = round(size * VIEW_H / VIEW_W)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{height}" '
        f'viewBox="0 0 {VIEW_W} {VIEW_H}" role="img" aria-label="{title}">\n'
        + svg_paths("  ")
        + "\n</svg>"
    )


def summary() -> dict[str, object]:
    """도면·콘솔 리터럴이 받아 가는 값."""
    return {
        "shapes": len(SHAPES),
        "blue": BLUE,
        "amber": AMBER,
        "viewW": VIEW_W,
        "viewH": VIEW_H,
        "widthMm": WIDTH_MM,
        "source": SOURCE_FILE,
    }
