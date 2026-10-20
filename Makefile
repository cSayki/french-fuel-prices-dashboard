PY ?= python3

.PHONY: install data run test clean

install:
	$(PY) -m pip install -r requirements.txt

data:
	$(PY) scripts/download_data.py
	$(PY) scripts/build_dataset.py

run:
	$(PY) -m streamlit run app.py

test:
	$(PY) tests/smoke_test.py

clean:
	rm -rf data/interim data/raw __pycache__ */__pycache__
