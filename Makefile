.PHONY: setup data api web dev test syntax

setup:
	bash scripts/setup-local.sh

data:
	python3 scripts/generate_sample_data.py

api:
	bash scripts/run-api.sh

web:
	bash scripts/run-web.sh

dev:
	bash scripts/run-local.sh

test:
	bash scripts/test.sh

syntax:
	python3 -m compileall -q backend/app scripts
