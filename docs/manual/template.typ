// ---------------------------------------------------------------------------
// Re:creon Player's Manual -- custom pandoc->typst template.
//
// Used by build.py:  pandoc ... --pdf-engine=typst --template=template.typ
//
// Deliberately self-contained: it does NOT use pandoc's bundled inner
// template (`conf`). Everything below is the manual's own typesetting.
// ---------------------------------------------------------------------------

// --- Palette ---------------------------------------------------------------

#let ink = rgb("#172033")
#let muted = rgb("#5a6478")
#let faint = rgb("#8a93a6")
#let hair = rgb("#d5dae3")
#let paper = rgb("#fcfcfa")
#let deep = rgb("#0b1124")
#let deep2 = rgb("#141d3a")
#let cyan = rgb("#0e7f8c")
#let cyan-bright = rgb("#6fd7e6")
#let amber = rgb("#b06f1f")
#let amber-bright = rgb("#d9994e")
#let cream = rgb("#e8e6df")

#let f-serif = ("Libertinus Serif", "Noto Serif", "DejaVu Serif")
#let rule-stroke = (paint: gradient.linear(amber, cyan), thickness: 1.2pt)
#let f-sans = ("Fira Sans", "DejaVu Sans", "Liberation Sans")
#let f-mono = ("JetBrains Mono", "DejaVu Sans Mono")

// --- pandoc metadata (set by build.py via -M) -------------------------------

#let m-title = "$if(title)$$title$$else$Player\'s Manual$endif$".replace("\'", "'")
#let m-version = "$if(version)$$version$$else$0.0$endif$"
#let m-date = "$if(date)$$date$$else$undated$endif$"
#let m-emblem = "$if(emblem)$$emblem$$else$logo.svg$endif$"

// --- Base document settings -------------------------------------------------

#set document(
  title: "Re:creon " + m-title,
  author: "The Re:creon project",
)

#let head-text(h) = h.body.at("text", default: "")

#set page(
  paper: "a4",
  margin: (top: 2.4cm, bottom: 2.2cm, x: 2.5cm),
  fill: paper,
  header: context {
    let chap = query(selector(heading.where(level: 1)).before(here())).at(-1, default: none)
    if chap != none {
      grid(columns: (1fr, auto),
        text(7.5pt, font: f-mono, tracking: .12em, fill: faint)[RE:CREON --- PLAYER'S MANUAL],
        text(7.5pt, font: f-mono, tracking: .06em, fill: faint)[#upper(head-text(chap))],
      )
      v(-4pt)
      line(length: 100%, stroke: .4pt + hair)
    }
  },
  footer: context {
    let chap = query(selector(heading.where(level: 1)).before(here())).at(-1, default: none)
    if chap != none {
      align(center)[
        #text(8pt, font: f-mono, fill: muted)[#counter(page).display("-- 1 --")]
      ]
    }
  },
)

#set text(
  font: f-serif,
  size: 10.5pt,
  fill: ink,
  lang: "en",
)
#set par(justify: false, leading: .78em, spacing: .95em)

#set heading(numbering: "1.1")
#set enum(numbering: "1.")

// --- Links, code, quotes -----------------------------------------------------

#show link: it => text(fill: cyan, underline(it))

#show raw.where(block: false): set text(font: f-mono, size: .85em, fill: deep2)
#show raw.where(block: false): it => box(fill: rgb("#eceef3"), radius: 2pt, inset: (x: 2.5pt, y: 1pt), baseline: 1pt, it)

#show raw.where(block: true): it => {
  set text(font: f-mono, size: 8.5pt)
  block(width: 100%, fill: rgb("#f0f2f6"), stroke: .5pt + hair, radius: 3pt,
    inset: 8pt, above: .6em, below: .6em, it)
}

#show quote: it => block(width: 88%, inset: (left: 12pt),
  stroke: (left: 1.2pt + amber), above: .4em, below: 1.2em, {
    set text(style: "italic", size: 9.5pt, fill: muted)
    it
  })

#show terms: set block(spacing: .8em)

// --- Tables ------------------------------------------------------------------

#show table: set text(font: f-sans, size: 8.5pt)
#show table: set table(
  inset: (x: 5pt, y: 3.5pt),
  stroke: (x: none, y: .5pt + hair),
)
#show table.header: it => {
  set text(fill: cream, weight: "bold")
  set cell(fill: deep2)
  it
}
#show figure: set figure.caption(position: top)
#show figure.caption: set text(font: f-mono, size: 8pt, fill: muted)

// --- Chapter icons -------------------------------------------------------------
//
// Small line drawings, keyed by the exact H1 title in the chapter sources.
// A new chapter that wants one adds its title here; unknown titles simply
// get no icon.

#let icon-box(size: 21pt, body) = box(width: size, height: size, baseline: 20%, body)

#let icon-about = icon-box()[
  #place(center + horizon, circle(radius: 10pt, stroke: .9pt + cyan, fill: none))
  #place(center + horizon, circle(radius: 5.5pt, stroke: .9pt + cyan, fill: none))
  #place(center + horizon, circle(radius: 1.9pt, fill: amber))
]
#let icon-start = icon-box()[
  #place(center + horizon, polygon((8pt, 0pt), (-4pt, -7pt), (-4pt, 7pt), fill: none, stroke: 1.1pt + cyan))
  #place(center + horizon, circle(radius: 1.9pt, fill: amber))
]
#let icon-worlds = icon-box(size: 24pt)[
  #place(center + horizon, circle(radius: 7.5pt, fill: deep2, stroke: 1.2pt + cyan-bright))
  #place(center + horizon, rotate(-16deg, ellipse(width: 23pt, height: 8pt, fill: none, stroke: 1.2pt + amber-bright)))
  #place(center + horizon, dx: 10pt, dy: -4pt, circle(radius: 1.5pt, fill: amber-bright))
]
#let icon-tech = icon-box()[
  #place(center + horizon, circle(radius: 2.2pt, fill: amber))
  #place(center + horizon, ellipse(width: 20pt, height: 8pt, stroke: .9pt + cyan, fill: none))
  #place(center + horizon, rotate(60deg, ellipse(width: 20pt, height: 8pt, stroke: .9pt + cyan, fill: none)))
  #place(center + horizon, rotate(-60deg, ellipse(width: 20pt, height: 8pt, stroke: .9pt + cyan, fill: none)))
]
#let icon-build = icon-box()[
  #place(center + horizon, rect(width: 15pt, height: 15pt, radius: 1.5pt, stroke: 1.1pt + cyan, fill: none))
  #place(center + horizon, dx: -7.5pt, dy: 0pt, line(length: 15pt, stroke: .9pt + amber))
  #place(center + horizon, dx: 0pt, dy: -7.5pt, line(length: 15pt, angle: 90deg, stroke: .9pt + amber))
]
#let icon-fleet = icon-box()[
  #place(center + horizon, polygon((9.5pt, 0pt), (-2.5pt, -7pt), (-2.5pt, -2.8pt), (1.8pt, 0pt), (-2.5pt, 2.8pt), (-2.5pt, 7pt), fill: cyan))
  #place(center + horizon, dx: -11pt, dy: 0pt, polygon((9.5pt, 0pt), (-2.5pt, -7pt), (-2.5pt, -2.8pt), (1.8pt, 0pt), (-2.5pt, 2.8pt), (-2.5pt, 7pt), fill: amber))
]
#let icon-combat = icon-box()[
  #place(center + horizon, circle(radius: 8.5pt, stroke: 1pt + cyan, fill: none))
  #place(center + horizon, dx: -11pt, dy: 0pt, line(length: 6pt, stroke: 1pt + cyan))
  #place(center + horizon, dx: 5pt, dy: 0pt, line(length: 6pt, stroke: 1pt + cyan))
  #place(center + horizon, dx: 0pt, dy: -11pt, line(length: 6pt, angle: 90deg, stroke: 1pt + cyan))
  #place(center + horizon, dx: 0pt, dy: 5pt, line(length: 6pt, angle: 90deg, stroke: 1pt + cyan))
  #place(center + horizon, circle(radius: 2.2pt, fill: amber))
]
#let icon-command = icon-box()[
  #place(center + horizon, rect(width: 17pt, height: 13pt, radius: 1.5pt, stroke: 1.1pt + cyan, fill: none))
  #place(center + horizon, dx: -8.5pt, dy: -3.2pt, line(length: 17pt, stroke: .8pt + cyan))
  #place(center + horizon, dx: -6.4pt, dy: -4.6pt, circle(radius: 1pt, fill: amber))
  #place(center + horizon, dx: -3.6pt, dy: -4.6pt, circle(radius: 1pt, fill: amber))
  #place(center + horizon, dx: -7.5pt, dy: 1.5pt, line(length: 9pt, stroke: .8pt + amber))
  #place(center + horizon, dx: -7.5pt, dy: 4.5pt, line(length: 11pt, stroke: .8pt + amber))
]
#let icon-scenarios = icon-box()[
  #place(center + horizon, dx: 0pt, dy: -5.5pt, polygon((0pt, -4pt), (9pt, 0pt), (0pt, 4pt), (-9pt, 0pt), fill: none, stroke: .9pt + cyan))
  #place(center + horizon, dx: 0pt, dy: 0.5pt, polygon((0pt, -4pt), (9pt, 0pt), (0pt, 4pt), (-9pt, 0pt), fill: none, stroke: .9pt + amber))
  #place(center + horizon, dx: 0pt, dy: 6.5pt, polygon((0pt, -4pt), (9pt, 0pt), (0pt, 4pt), (-9pt, 0pt), fill: paper, stroke: .9pt + cyan))
]
#let icon-glossary = icon-box()[
  #place(center + horizon, rect(width: 14.5pt, height: 15.5pt, radius: (left: 3pt), stroke: 1.1pt + cyan, fill: none))
  #place(center + horizon, dx: -4pt, dy: -7.75pt, line(length: 15.5pt, angle: 90deg, stroke: .9pt + cyan))
  #place(center + horizon, dx: -2pt, dy: -3.5pt, line(length: 6pt, stroke: .9pt + amber))
  #place(center + horizon, dx: -2pt, dy: 0pt, line(length: 6pt, stroke: .9pt + amber))
  #place(center + horizon, dx: -2pt, dy: 3.5pt, line(length: 6pt, stroke: .9pt + amber))
]
#let icon-appendix = icon-box()[
  #place(center + horizon, rect(width: 17pt, height: 14pt, radius: 1.5pt, stroke: 1.1pt + cyan, fill: none))
  #place(center + horizon, dx: -8.5pt, dy: -1.5pt, line(length: 17pt, stroke: .8pt + cyan))
  #place(center + horizon, dx: -8.5pt, dy: 3pt, line(length: 17pt, stroke: .8pt + cyan))
  #place(center + horizon, dx: -2.5pt, dy: -7pt, line(length: 14pt, angle: 90deg, stroke: .8pt + amber))
]

#let chapter-icons = (
  "About This Manual": icon-about,
  "Getting Started": icon-start,
  "Worlds and Their Economies": icon-worlds,
  "Technology and Research": icon-tech,
  "Construction": icon-build,
  "Fleets and Movement": icon-fleet,
  "Combat and Conflict": icon-combat,
  "Command Reference": icon-command,
  "Scenarios": icon-scenarios,
  "Glossary": icon-glossary,
  "Reference Tables": icon-appendix,
)

// --- Heading styles ------------------------------------------------------------

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  let key = head-text(it)
  let has-icon = key in chapter-icons
  let icon = if has-icon { chapter-icons.at(key) } else { [] }
  block(width: 100%, above: 1.5em, below: 1.6em)[
    #grid(
      columns: (if has-icon { (28pt, 1fr) } else { (1fr,) }),
      column-gutter: 10pt,
      align: left + horizon,
      icon,
      text(19pt, font: f-mono, weight: "bold", fill: ink)[#it],
    )
    #v(4pt)
    #line(length: 100%, stroke: rule-stroke)
  ]
}

#show heading.where(level: 2): it => block(above: 1.5em, below: .7em)[
  #box(width: 3pt, height: 1.05em + 1pt, fill: amber, radius: 1pt)
  #h(1em)
  #box({ set text(13pt, font: f-sans, weight: "bold", fill: cyan)
    it })
]

#show heading.where(level: 3): it => block(above: 1.2em, below: .5em)[
  #text(11pt, font: f-sans, weight: "bold", fill: deep2)[#it]
]

#show heading.where(level: 4): it => block(above: 1em, below: .4em)[
  #text(10.5pt, font: f-sans, weight: "bold", small-caps: true, fill: muted)[#it]
]

// --- Cover ----------------------------------------------------------------------

#let cover-stars = {
  let m = 2147483647.0
  let s = 4711.0
  let out = ()
  for i in range(130) {
    s = calc.rem(s * 16807.0, m)
    let x = s / m
    s = calc.rem(s * 16807.0, m)
    let y = s / m
    s = calc.rem(s * 16807.0, m)
    let w = s / m
    out.push((x, y, w))
  }
  out
}

#let corner-brackets = {
  // L-shaped ticks, each a 12mm curve anchored 10mm inside its cover corner.
  let tick(pts, anchor, dx, dy) = {
    let segs = pts.enumerate().map(((i, p)) =>
      if i == 0 { curve.move(p) } else { curve.line(p) })
    place(anchor, dx: dx, dy: dy)[#curve(fill: none,
      stroke: (paint: cyan-bright, thickness: 1.2pt, cap: "round", join: "round"), ..segs)]
  }
  tick(((0mm, 12mm), (0mm, 0mm), (12mm, 0mm)), top + left, 10mm, 10mm)
  tick(((0mm, 0mm), (12mm, 0mm), (12mm, 12mm)), top + right, -10mm, 10mm)
  tick(((0mm, 0mm), (0mm, 12mm), (12mm, 12mm)), bottom + left, 10mm, -10mm)
  tick(((0mm, 12mm), (12mm, 12mm), (12mm, 0mm)), bottom + right, -10mm, -10mm)
}

#let cover = {
  page(fill: deep, margin: 0pt, header: none, footer: none, numbering: none)[
    #box(width: 210mm, height: 297mm)[
      // starfield
      #for (x, y, w) in cover-stars {
        place(dx: x * 210mm, dy: y * 297mm)[#circle(radius: (.4 + w * 1.2) * 1pt,
            fill: (white, cyan-bright, rgb("#8fa6cc"), rgb("#57627f"))
              .at(calc.rem(calc.floor(w * 3.999), 4)))]
      }
      // a distant sun, peeking in at the lower left
      #place(bottom + left, dx: -38mm, dy: -30mm)[#circle(radius: 52mm, fill: deep2)]
      #place(bottom + left, dx: -38mm, dy: -30mm)[#circle(radius: 52mm, fill: none, stroke: (.8pt + amber-bright))]

      #corner-brackets

      // emblem
      #place(top + center, dy: 36mm, box(width: 64mm)[
        #image(m-emblem, width: 100%)
      ])

      // wordmark
      #place(top + center, dy: 118mm, {
        set align(center)
        text(29pt, font: f-mono, weight: "bold", fill: cream, tracking: .3em)[RE:CREON]
        v(1.3em)
        line(length: 44%, stroke: 1.4pt + amber-bright)
        v(1em)
        text(15pt, font: f-serif, style: "italic", fill: cyan-bright)[#m-title]
        v(2.4em)
        text(8.5pt, font: f-mono, fill: cream, tracking: .3em)[ANACREON: RECONSTRUCTION 4021]
      })

      // edition line
      #place(bottom + center, dy: -22mm, {
        set align(center)
        text(7.5pt, font: f-mono, fill: cream, tracking: .18em)[EDITION #m-version  --  #m-date]
        v(1em)
        text(7.5pt, font: f-mono, fill: rgb("#4a8f9c"), tracking: .12em)[A FAITHFUL RECREATION IN PYTHON]
      })
    ]
  ]
}

// ---------------------------------------------------------------------------
// Body as produced by pandoc.
// ---------------------------------------------------------------------------

$if(highlighting-definitions)$
// syntax highlighting functions from skylighting:
$highlighting-definitions$

$endif$
$for(header-includes)$
$header-includes$

$endfor$
$for(include-before)$
$include-before$

$endfor$
#cover
$if(toc)$

#page(header: none, footer: none)[
  #block(above: .5em)[
    #text(17pt, font: f-mono, weight: "bold", fill: ink)[Contents]
    #v(4pt)
    #line(length: 100%, stroke: rule-stroke)
  ]
  #set text(size: 9.5pt)
  // The outline lays the headings out again as its entries; inside this
  // scope they must render plain, or the pagebreak below would give every
  // chapter entry its own page.
  #show heading: it => (if it.level == 1 { it.body } else { default(it).body })
  #outline(title: none, indent: 18pt, depth: $toc-depth$)
]
$endif$

#counter(page).update(1)

$body$

$for(include-after)$

$include-after$
$endfor$
