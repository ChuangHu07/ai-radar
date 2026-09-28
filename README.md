# ai-radar

A Python script that fetches the latest AI-related papers from arXiv.

## Features

- Fetches recent AI-related papers from arXiv.
- Parses Atom/XML API responses.
- Displays paper titles, publication dates, and arXiv links.

## Requirements

- Python 3
- pip

## Installation

Install the required dependencies:

```bash
python -m pip install -r requirements.txt
```

## Installation

Clone the repository:

```bash
git clone https://github.com/ChuangHu07/ai-radar.git
cd ai-radar

-- Create a virtual environment:
python -m venv .venv

-- Activate the virtual environment:
Git Bash on Windows
source .venv/Scripts/activate

1. PowerShell on Windows
.\.venv\Scripts\Activate.ps1

2. macOS / Linux
source .venv/bin/activate

-- Install the required dependencies:
python -m pip install -r requirements.txt
```

## Usage

Run the script:

```bash
python fetch.py
```
When you run the script, it fetches the 20 latest AI-related papers from arXiv.
