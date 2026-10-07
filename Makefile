.PHONY: install backend frontend test backend-test

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && ./run.sh

frontend:
	cd frontend && npm run dev

# 后端测试：导出通道的口径、分页/全量一致、覆盖不追加、故障定位都在这里守护
backend-test:
	cd backend && .venv/bin/pip install -q -r requirements-dev.txt && .venv/bin/python -m unittest discover -s tests -v

test: backend-test
