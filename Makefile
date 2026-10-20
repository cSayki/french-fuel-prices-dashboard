PY ?= python3

.PHONY: install data run clean

install:
	$(PY) -m pip install -r requirements.txt

data:
	$(PY) scripts/download_data.py
	$(PY) scripts/build_dataset.py

run:
	$(PY) -m streamlit run app.py

clean:
	rm -rf data/interim data/raw __pycache__ */__pycache__
