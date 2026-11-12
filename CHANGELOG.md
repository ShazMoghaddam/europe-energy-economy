# Changelog

All notable changes to this project are listed here. Data refreshes that only bring in new figures are not listed;
see the pull requests labelled `data` for those.

## v1.0.0 (2026-11-11)

Launch of Energy & the Economy, with the State of Europe's energy report and the January 2027 challenge.

- **The report.** Eleven findings and 25 charts on Europe's energy from 2010 to October 2026: what normal looked like,
  the end of Russian gas, the 2022 price shock, the 2026 war in the Gulf, household bills, gas savings, the switch to
  clean power, what governments did and the profits of the big oil companies. Every number is worked out from the data
  by `findings/build.py`, so it stays true when new figures arrive.
- **Every Bezel Charts type.** The charts use all 15 types in [bezel-charts](https://pypi.org/project/bezel-charts/) 1.10.1:
  sparkline, line, area, bars, combo, waterfall, histogram, box plot, scatter, calendar heatmap, rings, donut, gauge,
  progress and bullet.
- **The data.** `data/fetch.py` downloads household prices, gas imports and gas use from Eurostat, oil and gas prices from
  FRED, and the electricity mix from Our World in Data. Company profits, the timeline of events and a few other figures
  are entered by hand, each with a link to its source.
- **January 2027 challenge: Two shocks.** Was 2026 as big a shock as 2022? A brief, three levels and starter code.
- **Checks.** Tests for the data and the report, a link checker, and a workflow that rebuilds every chart on each pull
  request and fails if the committed charts don't match the code.
- **Automatic refresh.** A weekly workflow downloads new figures and, only if they changed, opens a pull request with
  redrawn charts and an updated report.
- MIT licence, contribution guide, submission template, security policy, Dependabot, banner and social preview.
