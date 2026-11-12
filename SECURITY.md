# Security policy

This project is a data report and a monthly challenge. It has no website, server or user accounts, so the risks are
small, but they're taken seriously.

## Supported versions

Only the latest version on the `main` branch is supported. Fixes go straight into `main`.

## Reporting a vulnerability

Please report it privately, not in a public issue.

1. Open the [Security tab](https://github.com/ShazMoghaddam/europe-energy-economy/security) and press **Report a vulnerability**, or go straight to [a new advisory](https://github.com/ShazMoghaddam/europe-energy-economy/security/advisories/new).
2. Describe the problem and the steps that show it.

You'll get a reply within 7 days. Once the problem is confirmed, I'll agree a fix and a disclosure date with you, and
credit you in the advisory and the changelog unless you'd rather stay anonymous.

## Scope

In scope:

- The workflows in `.github/workflows/`, for example a way for a pull request to run code with write access or read secrets.
- `data/fetch.py` and `findings/build.py`, for example a downloaded file that could make them run code or write outside the repo.
- Charts or Markdown in this repo that could run script when viewed.

Out of scope:

- Problems in the data publishers' own websites (Eurostat, FRED, Our World in Data). Please report those to them.
- Problems in [bezel-charts](https://github.com/ShazMoghaddam/bezel-charts) itself. Please use its own [security policy](https://github.com/ShazMoghaddam/bezel-charts/security/policy).
- Code in `submissions/`, which belongs to the people who sent it. Read it before you run it.

A data error isn't a security issue, but it does matter. If a number looks wrong, please
[open an issue](https://github.com/ShazMoghaddam/europe-energy-economy/issues) with a link to the source.

---

Created by **Shaz Moghaddam** · London
[Website](https://shazmoghaddam.github.io) · [LinkedIn](https://www.linkedin.com/in/shazmoghaddam)
