PY ?= python3.11

venv:
	$(PY) -m venv .venv && .venv/bin/pip install -r requirements.txt

data:
	.venv/bin/python data/fetch_data.py

run:
	.venv/bin/streamlit run app.py

.PHONY: venv data run
