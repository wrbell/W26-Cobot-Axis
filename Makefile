.PHONY: lint fmt test typecheck spellcheck yamllint check install clean ci-local firmware

lint:
	ruff check src/bridge/

fmt:
	ruff check --fix src/bridge/

test:
	python -m pytest src/bridge/tests/ -v --cov=src/bridge --cov-fail-under=90 --cov-report=term-missing

typecheck:
	mypy src/bridge/ --exclude tests/

spellcheck:
	codespell --skip="vendor,*.json,.git,.coverage,*.xml" -L "ot"

yamllint:
	yamllint .github/workflows/

check: lint test typecheck yamllint spellcheck

install:
	pip install -r requirements.txt
	pre-commit install

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .coverage htmlcov .pytest_cache coverage.xml
	find . -name '*.pyc' -delete 2>/dev/null || true

ci-local:
	act -j lint-and-test --matrix python-version:3.11

firmware:
	@command -v arm-none-eabi-gcc >/dev/null || { echo "arm-none-eabi-gcc not found — install ARM toolchain first"; exit 1; }
	@test -d vendor/klipper || { echo "vendor/klipper not found — run: git clone --depth 1 https://github.com/Klipper3d/klipper.git vendor/klipper"; exit 1; }
	cp src/klipper_mods/stallguard_shared.h vendor/klipper/src/rp2040/
	cp src/klipper_mods/core1_stallguard.c vendor/klipper/src/rp2040/
	cp src/klipper_mods/stallguard_command.c vendor/klipper/src/rp2040/
	grep -q 'core1_stallguard' vendor/klipper/src/rp2040/Makefile || \
		sed -i'' -e '/rp2040\/i2c\.c/a\'$$'\n''src-y += rp2040/core1_stallguard.c'$$'\n''src-y += rp2040/stallguard_command.c' vendor/klipper/src/rp2040/Makefile
	grep -q 'core1_launch' vendor/klipper/src/rp2040/main.c || { \
		sed -i'' -e '/#include "sched.h"/a\'$$'\n''extern void core1_launch(void);' vendor/klipper/src/rp2040/main.c; \
		sed -i'' -e '/sched_main();/i\'$$'\n''    core1_launch();' vendor/klipper/src/rp2040/main.c; \
	}
	cd vendor/klipper && make olddefconfig && make -j$$(nproc)
	@echo "Firmware built: vendor/klipper/out/klipper.uf2"
