# browser-automation-builder
Desktop tool for Excel-driven browser form automation with Selenium and CustomTkinter

> **Use only on systems you are authorized to automate.** The browser is launched with relaxed security flags (`--disable-web-security` and related) so scripts can reach nested frames. Do not use this browser session for general web browsing.

## Features
- Step builder: type, select, click, press keys, wait
- Excel-driven: map columns to fields and run row by row
- Element inspector that captures XPaths
- Save and load step sequences as JSON
- Run log and exported pass/fail report

## Requirements
- Windows, Python 3.[VERSION]+, Microsoft Edge
- `pip install -r requirements.txt`

## Configuration
Copy `.env.example` to `.env` and set:
| Variable | Meaning |
|---|---|
| `SAP_URL` | [your target URL] |
| `SALESFORCE_URL` | [your target URL] |

## Quick start
1. `python MainAutomation.py`
2. Choose the platform and click **Open Browser**; sign in manually.
3. Load `examples/sample_data.xlsx`, add steps, click **Start**.


## Safety and limits
- Credentials are never stored; sign in manually.
- Failed rows are logged and the run continues.
- For SAP, it needed an API key
