.ONESHELL:
.PHONY: test
.PHONY: run_coverage
.PHONY: report_coverage
.PHONY: development-diff-cover
.PHONY:

define clone_official_repo
	git clone --depth 1 --branch "$(1)" https://github.com/CoinAlpha/hummingbot-professional.git full_repo
endef

define install_library
	rm -Rf full_repo
	mkdir full_repo
	$(call clone_official_repo,$(1))
	python3 -m pip install -f full_repo/library hummingbot
endef

test:
	coverage run -m nose --exclude-dir="test/connector" --exclude-dir="test/debug" --exclude-dir="test/mock"

run_coverage: test
	coverage report
	coverage html

report_coverage:
	coverage report
	coverage html

development-diff-cover:
	coverage xml
	diff-cover --compare-branch=origin/development coverage.xml

install_hb_dev_library:
	$(call install_library,development)

install_hb_master_library:
	$(call install_library,master)
