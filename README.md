# Mission game

```shell
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 app.py

# or
docker build -t biscofil/mission-game:v1.0.1 .
docker run --rm -v ./volume:/app/instance -p 8080:5000 biscofil/mission-game:v1.0.1
docker run --name mission-game -d --restart unless-stopped -v ./volume:/app/instance -p 8080:5000 biscofil/mission-game:v1.0.1
```
