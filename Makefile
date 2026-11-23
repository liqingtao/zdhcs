.PHONY: venv install fake test demo1 demo2

venv:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip

install: venv
	.venv/bin/python -m pip install -r requirements.txt

fake:
	.venv/bin/python -m demos.make_fake_screen

test:
	.venv/bin/python -m pytest -q

demo1:
	.venv/bin/python -m demos.demo1_pyautogui --screen assets/screenshots/fake_screen.png

demo2:
	.venv/bin/python -m demos.demo2_opencv

