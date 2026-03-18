FROM python:3.11-slim
WORKDIR /app
COPY web-requirements.txt .
RUN pip install --no-cache-dir -r web-requirements.txt
COPY sudoku_tutor.py sudoku_generator.py puzzles.py sudosolv.py ./
COPY web/ ./web/
EXPOSE 8080
CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8080"]
